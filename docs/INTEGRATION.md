# Seekr — Ranking-Tool Integration Guide

How to consume the Resource Intelligence Platform's read API from the internal
ranking/matching system. The platform provides **data only** — profiles,
evidence, provenance, and a change feed. All scoring, ranking, and
prioritization stays in your system.

Base URL: `https://finder-blond.vercel.app` (production) or `http://<host>:8000`
(local dev). Interactive OpenAPI docs at `/docs`. All responses are JSON.
All timestamps are UTC ISO-8601.

**Auth**: every `/v1` request needs `Authorization: Bearer <token>`. Get the
token from the platform team (it's the `RIP_API_TOKEN` Vercel env var).
Missing/wrong token → 401.

---

## The one rule: reference people by `person.id`

`person.id` is a UUID that never changes — not when new sources are attached,
not when profiles are re-fetched, not when merges are approved. Store it as
your foreign key.

Two events move data between IDs, and both keep old IDs resolvable:

- **Split** (operator undoing a bad merge): change feed shows `field: "split"`
  with `new_value: "person:<new-uuid>"`.
- **Merge** (operator confirming two persons are one): the losing ID becomes a
  tombstone — `GET /v1/persons/{old-id}` returns the canonical person's full
  profile with `requested_id` set to what you asked for, and every profile
  carries a `merged_into` field (null for live persons). Change feed shows
  `field: "merge"`. Merged persons stop appearing in `/v1/persons` listings.

---

## Endpoints

### Lookup and filtering

```
GET /v1/persons?q=<name substring>&skill=<exact value>&organization=<substring>&limit=50&offset=0
GET /v1/persons/{id}
```

`skill=` matches evidence of types `skill`, `research_interest`, and
`specialization` (exact, case-insensitive). Filters are for *finding* records;
ordering is insertion-order — deliberately not relevance-ranked.

Example person:

```json
{
  "id": "8ba25591-5ff5-4086-811d-7179ae8ee02b",
  "canonical_name": "Geoffrey E. Hinton",
  "aliases": ["G. Hinton", "Geoffrey Hinton", "Hinton, G."],
  "location": null,
  "current_role": null,
  "current_organization": "University of Toronto",
  "profile_urls": [
    "http://www.cs.toronto.edu/~hinton/",
    "https://dblp.org/pid/10/3248",
    "https://en.wikipedia.org/wiki/Geoffrey_Hinton",
    "https://scholar.google.com/citations?user=JicYPdAAAAAJ"
  ],
  "created_at": "2026-08-17T19:16:59.623235",
  "updated_at": "2026-08-17T19:21:12.816316"
}
```

Top-level scalar fields (`location`, `current_role`, ...) are **first-observed
values** — conveniences, not truth. For anything your scoring depends on, use
the evidence endpoint, which carries source, confidence, and conflicts.

The person response also includes an **`attributes` aggregate**: each distinct
claim with `evidence_count`, `max_confidence`, and the list of `sources`
attesting it — a ready-made corroboration signal without fetching raw
evidence:

```json
{"attribute_type": "skill", "value": "Python", "evidence_count": 2,
 "max_confidence": 0.85, "sources": ["github", "stackoverflow"]}
```

### Evidence — the substrate for scoring

```
GET /v1/persons/{id}/evidence?attribute_type=skill
```

```json
{
  "evidence": [
    {
      "attribute_type": "award",
      "value": "Turing Award (2018)",
      "extracted_info": null,
      "source": "dblp",
      "url": "https://dblp.org/pid/10/3248",
      "source_record_id": 114,
      "observed_at": "2026-08-17T19:21:12.767833",
      "published_at": null,
      "confidence": 0.85,
      "verification_state": "unverified"
    }
  ]
}
```

Semantics your scorer should know:

- **`attribute_type`** values currently emitted: `skill`, `research_interest`,
  `award`, `affiliation`, `location`, `bio`. New types may appear; ignore
  unknown ones rather than failing.
- **`confidence`** (0-1) is *extraction* confidence — how sure the platform is
  that the source really asserts this — not importance. A skill backed by 40
  repositories gets higher confidence than one backed by 2.
- **`verification_state`**: `unverified` (one source) → `corroborated`
  (2+ independent sources make the same claim). Treat `corroborated` as a
  strong quality signal.
- **Conflicts are preserved, not resolved.** If sources disagree on location,
  you will see one evidence row per claimed value. Resolve (or score the
  ambiguity) in your system.
- `extracted_info` is a human-readable justification, e.g.
  `"19991 answers, total score 269851 on Stack Overflow"` — useful for
  explaining scores to users.

### Publications, projects, organizations

```
GET /v1/persons/{id}/publications   → title, venue, date, DOI, citations, topics, author_position
GET /v1/persons/{id}/projects       → name, url, technologies, activity {stars, downloads, ...}, role
GET /v1/persons/{id}/organizations  → org, relation (worked_at | studied_at), role, dates, is_current
GET /v1/persons/{id}/conflicts      → attribute disagreements, both sides with provenance
GET /v1/persons/{id}/graph          → immediate neighborhood (see below)
GET /v1/persons/{id}/documents      → published CV/résumé links + profile pages
```

### Documents

```json
{"cvs":[{"url":"https://example.edu/~a/cv.pdf",
         "found_on":"https://example.edu/~a/",
         "evidence":"linked as \"Curriculum Vitae\" on https://example.edu/~a/",
         "source":"web","confidence":0.8}],
 "profiles":[{"url":"https://dblp.org/pid/10/3248","kind":"bibliography"}]}
```

Every CV link was found on a page Seekr fetched, with `found_on` and the
anchor text that identified it — **no URL is ever constructed or guessed, and
Seekr does not host or generate documents**. A link may still 404 if the owner
removed it; `observed_at` tells you when it was last seen.

### Graph

```
GET /v1/persons/{id}/graph?depth=1&limit_coauthors=20
```

```json
{"nodes":[{"id":"<uuid>","type":"person","label":"Ada Example"},
          {"id":"org-12","type":"organization","label":"Acme Labs"}],
 "edges":[{"from":"<uuid>","to":"org-12","type":"worked_at","role":"Engineer","is_current":true},
          {"from":"<uuid>","to":"<uuid2>","type":"coauthor","shared_publications":3,
           "via_publication_id":42}]}
```

`shared_publications` is a factual edge weight (how many papers two people
co-authored), not a ranking of people; `limit_coauthors` exists only to bound
the payload. Depth is 1 — call again per node to walk further.

### Natural-language search

```
GET /v1/query?q=distributed systems at Acme Labs, top 10[&discover=true]
```

Paging: `limit` (default 50, max 500) and `offset`. The response reports
`total_matches` (everything the filters match) alongside `count` (this page),
plus `has_more` and `next_offset` — so a caller always knows the true size of
a result set rather than assuming the page is all there is.

Terms are matched against the live corpus vocabulary. The response always
reports `applied_filters` and `unmatched_terms` — **never assume a constraint
you sent was enforced; check that it appears in `applied_filters`.** Results
are in DB order, not relevance order.

`discover` is a three-way opt-in, and none of the modes ingest during the
request:

| value | behavior |
|---|---|
| `false` (default) | local corpus only |
| `true` | also returns `discovery_suggestions` from live searches across OpenAlex, Semantic Scholar and dblp; nothing is stored |
| `queue` | same, plus each suggestion is added to the discovery-lead queue and `queued_leads` reports how many; a worker ingests them later under the normal rate limits |

`true` and `queue` both **store** any result that arrived with a full person
payload, and report the count as `stored_from_live`. Those people are then
returned as ordinary results and are answerable from the graph afterwards; the
same query will not be bought again for 7 days. `discover=false` (the default)
remains strictly read-only.

When filters combine to zero, `empty_reason` names the filter responsible —
e.g. *"Dropping skills (growth) would return 2"* — so an empty result set is
diagnosable rather than mysterious.

Suggestions carry `source`, `external_id`, `name`, `reason` and an
`ingest_command`. They are candidates, not results, and are not ranked.

Publications are deduplicated by DOI across sources (an OpenAlex record and a
dblp record of the same paper are one row). `activity` keys vary by source
(GitHub: stars/forks; Hugging Face: likes/downloads) — treat it as an open map.

### Provenance — "where did this come from?"

```
GET /v1/persons/{id}/provenance
```

```json
{
  "sources": [
    {"source": "openalex", "external_id": "A5110248343",
     "match_method": "new", "match_confidence": 1.0},
    {"source": "dblp", "external_id": "10/3248",
     "match_method": "fuzzy:name+org", "match_confidence": 0.75,
     "match_signals": {"name_score": 100.0, "shared_org": "university of toronto"}}
  ]
}
```

`match_method` tells you how each source was attached to this person:

| method | meaning | suggested trust |
|---|---|---|
| `new` | first source for this person | n/a |
| `strong:orcid` / `strong:email` / `strong:username` / `strong:url` | deterministic shared identifier | very high |
| `fuzzy:name+org` | name similarity + shared organization | high once approved (see `review_state`), moderate otherwise |
| `split:manual` | operator detached this record from a wrong merge | high |

Each source also carries **`review_state`**: `unreviewed`, `approved` (a human
confirmed the merge), or `split`. If your scoring is identity-sensitive,
down-weight claims whose only source is an `unreviewed` + `fuzzy:*` link.
Strong-key links need no review.

Near-miss pairs that did *not* merge are queued for human review instead of
being silently forked; they never affect what you read.

---

## Sync patterns

### Initial backfill

Page through `GET /v1/persons?limit=500&offset=...` until a page returns fewer
than `limit` rows, fetching sub-resources per person as needed.

### Incremental updates (recommended: poll the change feed)

```
GET /v1/changes?since_id=<your last cursor>&limit=5000
```

Returns field-level changes in a stable order plus `next_cursor` (integer) and
`has_more`. **Use the integer `since_id` cursor** — it is monotonic, has no
clock-skew or same-timestamp-tie issues, and `has_more: true` means loop
immediately with the new cursor. The old timestamp `since` param still works
for backward compatibility.

```json
{
  "changes": [
    {"person_id": "275f41e6-...", "field": "current_organization",
     "old_value": null, "new_value": "Wesleyan University",
     "changed_at": "2026-08-17T19:16:56.181803", "source_record_id": 1}
  ],
  "next_since": "2026-08-17T19:16:56.181803"
}
```

Fields you'll see: person scalars (`canonical_name`, `location`, ...),
`conflict:<field>` (a source disagreed with the stored value),
`conflict_detected:<field>` (the same disagreement rendered for consumers:
`new_value` reads `"Berlin (github) vs Zurich (orcid)"`, so you can react to
conflicts from the feed alone without polling `/conflicts`),
`key_collision:<type>` (identity signal claimed by two persons — resolution
edge case), `merge`, and `split` (see above). A person appearing for the first
time shows as `canonical_name: null → <name>`.

### Push instead of poll (webhooks)

```
POST /v1/webhooks   {"url": "https://you.example/hook", "event_types": ["person.updated","person.conflict"]}
GET  /v1/webhooks
DELETE /v1/webhooks/{id}
```

The response to `POST` includes `signing_secret` **once**. Every delivery
carries:

```
X-RIP-Signature: sha256=<hmac-sha256 of the exact request body>
X-RIP-Event: person.updated | person.conflict
X-RIP-Delivery-Id: <int>
```

Verify by HMAC-ing the raw bytes you received — the body is serialized once
and those same bytes are signed, so no re-serialization is needed. Payload:

```json
{"event_type":"person.updated","sequence_id":8412,"person_id":"...",
 "field":"current_organization","old_value":null,"new_value":"Acme Labs",
 "occurred_at":"2026-08-18T03:00:11Z"}
```

`sequence_id` is the same integer cursor as `/v1/changes`, so a missed
delivery is recoverable by polling from your last seen id — deliveries are
at-least-once, and duplicates are safe to ignore by `X-RIP-Delivery-Id`.

Deliveries are written in the same transaction as the change (an outbox) and
sent afterwards by the ingest host, so you will never be notified about a
change that was rolled back. Note that pushes originate from wherever
ingestion runs, not from the read API deployment.

**Webhooks are best-effort push — keep polling `/v1/changes` as your source of
truth.** Nothing is sent until `rip.cli deliver-webhooks` runs on the ingest
host, so a stalled cron delays (never loses) deliveries; failures stop after 3
attempts. `GET /v1/webhooks/health` reports the backlog:

```json
{"active_subscriptions":2,"pending":0,"delivered":1841,"failed":0,
 "last_delivery_at":"2026-08-18T03:00:12Z","oldest_pending_at":null}
```

A rising `pending` or an old `oldest_pending_at` means delivery is not running;
your `/v1/changes` cursor will still be complete.

Simplest consumer loop: collect distinct `person_id`s from the feed,
re-fetch those profiles, upsert into your store, save `next_since`.

### Freshness

`last_observed` in provenance tells you when each source was last re-checked.
The platform re-fetches stale sources on a schedule (`refresh` job); nothing
is ever silently deleted — data only gets added, corroborated, or conflicted.

---

## Operational endpoints

```
GET /v1/health/sources      → ingestion run counts + last run per source (ok/error)
GET /v1/review/merges       → merges awaiting human review (mostly for our ops, readable by you)
```

## What this API will never do

No candidate scores, talent scores, relevance ordering, recommendations, or
prioritization — by design. If you find yourself wanting those from this API,
that logic belongs in your system; what you can ask of this platform is more
*data*: new sources, new attribute types, richer evidence.

## Requests / errors

- 404 on unknown person IDs; standard FastAPI validation errors (422) on bad params.
- 401 on missing/invalid bearer token (see Auth above).
- Limits: `persons` max 500/page, `changes` max 5000/page.
- The production deployment serves a read-only snapshot; data updates arrive
  by redeploy. `updated_at` / `last_observed` tell you how fresh a record is.
