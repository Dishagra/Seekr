# Seekr

*Resource intelligence platform — worldwide people discovery*

**New here? Read [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md)** — what Seekr is,
how it works, and what it can and cannot do, in plain language. This file is
the operator reference.

A data layer that discovers, collects, normalizes, and maintains **evidence-backed
profiles of publicly discoverable people** — specialized experts and strong
generalists — and exposes them through a clean read API.

**`/v1/query` ranks; `/v1/persons` does not.** Natural-language search orders
results by how well the evidence backs what was asked — see [Relevance
ranking](#relevance-ranking). The faceted filter API stays deliberately
unordered, so a downstream tool can still apply its own scoring to a raw
match set.

```
Internet / External Sources
        ↓
Source → Connector → Raw SourceRecord → Normalizer → Entity Resolution → Resource DB
        ↓
Resource API  (stable IDs, evidence, provenance, change feed)
        ↓                              ↓
/v1/persons  (filters, unordered)   /v1/query  (filters + relevance ranking)
```

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# ingest
.venv/bin/python -m rip.cli search-openalex "Geoffrey Hinton"   # find author IDs
.venv/bin/python -m rip.cli ingest openalex A5110248343
.venv/bin/python -m rip.cli ingest github torvalds

# serve everything — API at /docs, UI at /ui. Reads .env for API keys.
.venv/bin/python -m rip.cli serve

# keep data fresh (run from cron)
.venv/bin/python -m rip.cli refresh --older-than-hours 24

# review suspicious merges and possible duplicates (also available via API)
.venv/bin/python -m rip.cli review list
.venv/bin/python -m rip.cli review approve 114   # confirm a fuzzy merge
.venv/bin/python -m rip.cli review split 22      # undo one: detach into new person
.venv/bin/python -m rip.cli review merge 7       # fold a possible-duplicate pair together
.venv/bin/python -m rip.cli review dismiss 7     # or mark the pair as distinct people

# re-run parsers over stored raw payloads (no network; after parser improvements)
.venv/bin/python -m rip.cli reparse

# bulk load a JSONL(.gz) dump; blocked resolution keeps this sub-quadratic
.venv/bin/python -m rip.cli bulk-ingest openalex --file authors.jsonl --batch-size 500

# continuous lead worker (separate process from `serve`; SQLite WAL handles both)
.venv/bin/python -m rip.cli worker --poll-interval 30 --limit 25

# how big is the backlog, and how long will it take?
.venv/bin/python -m rip.cli queue-stats
# one-time catch-up: large batch, no enrichment (safe without API tokens)
RIP_LEAD_BATCH=500 .venv/bin/python -m rip.cli worker --limit 500 --once --no-enrich

# environment / queue-depth sanity check
.venv/bin/python -m rip.cli check-db

# push queued change events to webhook subscribers
.venv/bin/python -m rip.cli deliver-webhooks

# bulk discovery: mine stored records for new people, then drain the queue
.venv/bin/python -m rip.cli discover                        # co-authors (no API calls)
.venv/bin/python -m rip.cli discover --github-contributors  # + repo contributors (live)
.venv/bin/python -m rip.cli ingest-leads --limit 25

# tests
.venv/bin/python -m pytest tests
```

Environment:

| Variable | Purpose |
|---|---|
| `RIP_DATABASE_URL` | SQLAlchemy URL (default `sqlite:///rip.db`; use Postgres in production) |
| `GITHUB_TOKEN` | Optional. Raises GitHub rate limit from 60/h to 5000/h |
| `OPENALEX_MAILTO` | Optional. Joins the OpenAlex polite pool |

## Data model

- **Person** — stable UUID, canonical name, aliases, location, current role/org,
  profile URLs. The UUID never changes, so the ranking tool can reference it
  even as external profiles change.
- **SourceRecord** — one raw capture per external profile (`source` +
  `external_id` unique). Immutable-ish; never destroyed by merging. Carries
  `first_observed`, `last_observed`, `extracted_at`, and a `content_hash` for
  change detection.
- **IdentityLink** — the resolution decision binding a SourceRecord to a
  Person, with `match_method`, `match_confidence`, and the signals used.
  Every merge is auditable and reversible.
- **PersonKey** — strong identifiers (ORCID, email, `github:login`,
  normalized URLs) used for deterministic resolution.
- **Evidence** — every attribute claim (skill, research interest, role,
  education, location, bio, …) is a row pointing at the SourceRecord it came
  from, with confidence and `verification_state`
  (`unverified` → `corroborated` when a second source makes the same claim).
- **Organization / Affiliation** — `worked_at` / `studied_at` edges with roles
  and dates.
- **Publication / Authorship** — deduped by DOI or source ID; author position
  preserved.
- **Project / Contribution** — repos and other projects with technologies and
  activity metrics.
- **ChangeLog** — field-level change history; also records conflicts and key
  collisions. Powers the incremental `/v1/changes` feed.
- **IngestionRun** — per-fetch status for source health monitoring.

### Conflicts are preserved, never overwritten

If GitHub says "Berlin" and a later source says "Zurich", the Person keeps the
first value, a `conflict:location` ChangeLog row is written, **both** location
Evidence rows remain queryable, and a first-class `attribute_conflict` row
records both sides with their provenance (`GET /v1/persons/{id}/conflicts`).
"Where did we get this?" is always answerable via
`/v1/persons/{id}/provenance`.

## Entity resolution

Order of strategies (see `backend/rip/resolution.py`):

1. **Deterministic** — any strong key already attached to a person
   (ORCID, public email, source username, normalized profile/website URL)
   → merge, confidence 0.97.
2. **Fuzzy** — name similarity ≥ 92 (token-sort) **and** a shared
   organization → merge, confidence 0.75.
3. Otherwise → new person.

Source records survive merging; only IdentityLinks are added. Key collisions
(a strong key claimed by two persons) are logged rather than silently
reassigned.

## API contract (for the ranking tool)

| Endpoint | Purpose |
|---|---|
| `GET /v1/persons?...` | faceted people search — see filter table below (no ranking) |
| `GET /v1/facets?field=` | available filter values + how many people carry each |
| `GET /v1/query?q=` | natural-language search: query parsed into filters against the live vocabulary; response lists `applied_filters` and `unmatched_terms` honestly; results ranked by evidence, each carrying `score` + `score_components` |
| `GET /ui` | internal exploration UI (archive-styled; token pasted in-page) |
| `GET /v1/persons/{id}` | profile by stable UUID |
| `GET /v1/persons/{id}/evidence?attribute_type=` | evidence with confidence + verification state |
| `GET /v1/persons/{id}/publications` | publications + author position |
| `GET /v1/persons/{id}/projects` | projects + contribution role |
| `GET /v1/persons/{id}/organizations` | affiliation history |
| `GET /v1/persons/{id}/provenance` | which sources, matched how, observed when |
| `GET /v1/persons/{id}/documents` | published CV/résumé links and profile pages — **only links found on pages we fetched; Seekr never creates or hosts a document** |
| `GET /v1/changes?since_id=` | incremental sync feed (integer cursor + `has_more`; legacy `since` timestamp still accepted) |
| `POST /v1/review/duplicates/{id}/merge` \| `/reject` | act on near-miss duplicate candidates |
| `GET /v1/health/sources` | ingestion run status per source |
| `GET /v1/review/merges` | suspicious merges: fuzzy matches, heavily-linked persons, key collisions |
| `POST /v1/review/merges/{link_id}/approve` | mark a fuzzy merge as human-verified |
| `POST /v1/review/merges/{link_id}/split` | undo a merge: detach that source record (and all rows it produced) into a new person |

OpenAPI docs at `/docs` when serving.

## Relevance ranking

`GET /v1/query` filters first, then ranks the matches. Filtering decides who is
eligible; ranking decides who leads. Every result carries `score` and
`score_components`, so a position in the list is always traceable to evidence
rather than asserted:

```json
{ "canonical_name": "Abhishek Veeramalla", "score": 0.414,
  "score_components": { "depth": 0.27, "confidence": 0.9,
                        "corroboration": 0.0, "breadth": 0.431, "recency": 0.5 } }
```

| Signal | Weight | What it measures |
|---|---|---|
| `depth` | 0.25 | How much evidence backs the thing you asked for. A free-text bio mention counts at ¼ of a stated skill — it separates someone from nobody without outranking a decade of commits. |
| `output` | 0.25 | Work they actually shipped, and how far it landed: repository stars and forks, publication citations. On-topic work counts fully; unrelated work at ¼, so a famous side project never outranks someone who built the thing you asked about. |
| `confidence` | 0.15 | How strongly the source stated it. GitHub scales this by repository count, so it carries much of the volume signal for developers. |
| `recency` | 0.15 | Age of the newest thing we can date — a repository still being pushed to, a paper published, dated evidence — on a 2-year half-life. Undated scores a neutral 0.5: most sources never state a date, and treating "unknown" as "ancient" would bury the entire GitHub corpus. Off-topic work never sets recency, or a side repo would make a dormant specialism look current. |
| `corroboration` | 0.10 | Independent sources making the same claim (`verification_state = corroborated`). Needs enrichment, and needs the sources to share a strong key. |
| `breadth` | 0.10 | How many sources know this person at all, split merges excluded. |

**Projects and publications are one signal on purpose.** Stars and citations
are the same kind of evidence — work put out and taken up — and scoring them
separately would mean a developer outranks a researcher for reasons of source
rather than merit.

Counts are log-scaled to saturation points (12 evidence rows, 4 sources, 5,000
combined stars + citations): the 20th repository should not outweigh everything
else. Ties keep filter order, so equal-evidence results stay stable across
pages.

A deliberately plain linear blend, not a learned model — every result can
explain itself, and `match_feedback` has to accumulate real judgements before
anything can be trained on them. Weights live in `WEIGHTS` in `rip/nlq.py`.

**Two-stage retrieval.** Ranking needs to see the field before it can pick a
winner, so the filter yields a candidate pool (`RIP_CANDIDATE_POOL`, default
500) that is scored and *then* paged. `total_matches` still reports the true
filter count; paging deeper than the pool is not a meaningful request of a
ranked list.

Set `RIP_VOCAB_TTL` (default 60s) to tune how long the query vocabulary is
cached — it is four `SELECT DISTINCT`s over the corpus, and rebuilding it per
request costs more than everything else in a query put together.

## Search filters

`GET /v1/persons` accepts these, combined with AND. Every one is a *filter*;
`sort` only reorders by a factual field and never by fitness for a role.

| Parameter | Matches |
|---|---|
| `q` | name or alias substring |
| `skill` | skill, research interest or specialization (substring) |
| `organization` | any affiliation, current or past |
| `current_organization` | present employer only |
| `education` | where they studied (`studied_at` affiliations) |
| `role` | job title, current or historical |
| `country` | ISO-3166 alpha-2 (`IN`, `US`, `DE`) — structured, not string matching |
| `location` | free-text place |
| `source` | has a record from this source (`github`, `orcid`, …) |
| `technology` | technology used in one of their projects |
| `min_publications` / `min_citations` | scholarly output thresholds |
| `min_sources` | corroborated across at least N sources |
| `active_since` | published since `YYYY` or `YYYY-MM-DD` |
| `updated_since` | Seekr record changed since a timestamp |
| `has_cv` / `has_email` | has a published CV link / public email |
| `sort` | `relevance` (insertion order), `recent`, `name` |
| `limit` / `offset` | paging; response carries `total_matches`, `has_more`, `next_offset` |

`GET /v1/facets?field=country|source|organization|skill|role` lists the values
actually present in the corpus with people-counts, so a UI can build filter
menus from live data instead of a hardcoded list.

## Connectors

| Connector | API | Identifier | Notes |
|---|---|---|---|
| `github` | api.github.com (official REST) | username | languages → skill evidence, top repos → projects, company → affiliation, blog/twitter → resolution links |
| `openalex` | api.openalex.org (fully open) | author ID | covers the scholarly graph (arXiv, journals, conferences); ORCID → strong identity key; topics → research interests; top-cited works → publications |
| `orcid` | pub.orcid.org public API (no key) | ORCID iD | employment/education history with roles + dates, keywords → research interests, researcher URLs → resolution links, works → publications (deduped by DOI against OpenAlex) |
| `stackoverflow` | api.stackexchange.com v2.3 | numeric user ID | top answer tags → skill evidence weighted by answer volume, website → resolution link. `STACKEXCHANGE_KEY` raises daily quota 300 → 10k |
| `dblp` | dblp.org (open, no key, 2s courtesy interval) | dblp PID | CS bibliography: homepage/Scholar/Wikipedia/Wikidata URLs → strong resolution keys, affiliations, awards, publications with co-author PIDs → discovery |
| `huggingface` | huggingface.co/api (public, no key) | username | org memberships → affiliations, models/datasets → projects, pipeline tags + libraries → ML skill evidence |
| `semanticscholar` | api.semanticscholar.org (official Graph API, no key; `SEMANTIC_SCHOLAR_API_KEY` for higher limits) | author ID | homepage → resolution link, affiliations, h-index/citations as evidence, papers deduped by DOI |
| `exa` | api.exa.ai (**paid**, `EXA_API_KEY`) | Exa person id | the only source reaching non-academic roles: job title, employer, work history, location. **Records are LinkedIn-derived** — see the note below |
| `web` | any public page, one URL at a time | URL | robots.txt honored before fetching; JSON-LD Person, Open Graph, ORCID, displayed emails, links to known profile hosts. No spidering |

### Auto-enrichment

Every ingest follows the identity signals it finds — an ORCID in a GitHub bio,
an OpenAlex ID on an ORCID record, a homepage on a dblp page — up to 3 hops,
skipping sources already stored and never letting a failed hop fail the root
ingest (`backend/rip/enrich.py`). So `ingest github <user>` can yield a GitHub +
ORCID + OpenAlex + homepage profile in one command. Disable with
`--no-enrich`.

Adding a source = one file in `backend/rip/connectors/` emitting a
`NormalizedProfile` (see `backend/rip/normalize.py`) + one registry line in
`backend/rip/connectors/__init__.py`. Nothing in the core pipeline changes.

The base connector (`backend/rip/connectors/base.py`) provides polite HTTP: minimum
request interval, retry with backoff on 5xx, rate-limit detection
(429 / `x-ratelimit-remaining`) honoring `Retry-After`.

### Finding people who aren't researchers

Nine of the ten connectors index scholarly or open-source output, so someone
with no publications and no public code is invisible to them. `exa` is the
exception and the only way Seekr answers "product designers at Swiggy".

**Know what you are ingesting.** Exa's person records are largely derived from
LinkedIn profiles. Seekr does not crawl LinkedIn — Exa is queried under a
commercial agreement and is responsible for its own index — but these are
personal records about identifiable people who did not consent to being in
your database. The originating URL is stored on every record so provenance is
never hidden, and `exa` is tried **last** in live discovery so the free
scholarly sources answer first and you only spend money when they cannot.
Decide your lawful basis and retention policy before ingesting at volume.

### Live search feeds the graph (pay once, not per query)

When a live provider returns a whole person record — Exa does — that record is
ingested immediately. The data is already bought; discarding it would mean
paying for the same people again next week. Two consequences:

- results appear as ordinary search results, not just as suggestions, because
  the query is re-parsed after storing (a company we had never heard of is a
  real filter once its people are in the graph)
- a `search_cache` row records each provider/query pair, so repeating a query
  within `SEEKR_SEARCH_TTL_DAYS` (default 7) skips the paid call entirely

Keyed on your original query, not the leftover words — otherwise storing new
people changes the residual string and the same request bills twice.

The free scholarly sources (OpenAlex, Semantic Scholar, dblp) return only an
identifier, so their full profile has to be fetched — but that fetch is free,
so up to `MAX_FREE_FETCHES` (10) per query are pulled and stored too. A query
the corpus cannot answer therefore grows the corpus.

People found this way are returned as results and flagged `from_live_search`
(shown as a **new** tag in the UI). They deliberately bypass the corpus
filter: that filter can only express what the corpus already knows, so a
person fetched seconds ago would fail it and the round-trip would be wasted.

### Topical discovery, not surname matching

Asking OpenAlex for "Rust developers" by author name returns people *surnamed*
Rust. Topical queries instead search works and take those works' authors, so
"computer vision researchers" returns Zisserman, Simonyan and Szeliski. Author
name search remains the fallback when the topical search finds nobody.

Scholarly indexes also carry entity records that are not people — "Computer
Vision Syndrome", "European Conference on Computer Vision", lab names. These
are rejected before ingest rather than becoming persons in the graph.

### Web search and page rendering (free tiers)

These are infrastructure, not people sources: they find URLs and fetch pages.

| Provider | Env var | Free tier | Used for |
|---|---|---|---|
| Tavily | `TAVILY_API_KEY` | 1,000 credits/month | finding homepages |
| SerpApi | `SERPAPI_API_KEY` | 250 searches/month | homepage search fallback |
| Firecrawl | `FIRECRAWL_API_KEY` | 1,000 credits/month | rendering JS-heavy pages |
| ZenRows | `ZENROWS_API_KEY` | 5,000 credits/month | render fallback |
| ScrapingBee | `SCRAPINGBEE_API_KEY` | 1,000 trial credits | render fallback |

```bash
# find homepages for people who have none, then read them
python -m rip.cli find-homepages --limit 20 --min-sources 2
```

Each is skipped when its key is unset, so a default install makes no
third-party calls. **robots.txt is always checked before any renderer** — the
render services exist for pages that are technically hard, never to reach a
page whose owner disallowed us.

### India-focused harvesting

The corpus is India-first. Two pipelines reach Indian people at scale:

```bash
# India-affiliated researchers (2.67M available in OpenAlex)
python -m rip.cli harvest openalex --india --out india.jsonl --limit 30000 \
  --filter "works_count:>20"
python -m rip.cli bulk-ingest openalex --file india.jsonl

# India-located developers (608k on GitHub; needs GITHUB_TOKEN for volume)
python -m rip.cli harvest github --india --out india_gh.jsonl --limit 5000
python -m rip.cli bulk-ingest github --file india_gh.jsonl
```

GitHub caps any one search at 1,000 results, so `harvest github --india`
slices by city (25 hubs from Bengaluru to Bhubaneswar) and then by follower
band within each city. OpenAlex uses `last_known_institutions.country_code:IN`
and has no such cap — resume a long harvest with `--cursor`.

**Sources deliberately excluded after checking:** Vidwan (INFLIBNET's national
expert database) publishes `robots.txt` with `Disallow: /` for every agent
except Googlebot, so it is off limits despite being the ideal source.
Shodhganga's OAI-PMH endpoint is misconfigured upstream and unreachable.
LinkedIn and Naukri forbid automated access in terms you accept by using them.

### Candidate next connectors (in rough value order)

1. **Apollo (licensed API)** — professional/company data, where the plan permits
2. **Personal websites / blogs** — respectful fetch honoring robots.txt
3. **Kaggle** — requires API credentials
4. **arXiv API** — deliberately skipped for now: no author IDs (name-only
   matching is too weak for safe resolution) and OpenAlex already indexes
   arXiv papers

## Bulk discovery

`backend/rip/discover.py` mines existing source records for people not yet ingested
and queues them as `DiscoveryLead` rows (unique per source+identifier,
skipping anyone already ingested):

- **OpenAlex co-authors** — raw-only, zero extra API calls
- **dblp co-authors** — raw-only, co-author PIDs from stored records
- **GitHub contributors** — bounded live calls: top 3 starred repos per known
  person, top 10 contributors each, bots excluded

`ingest-leads --limit N` drains the queue through the normal pipeline, so
discovery volume never outruns rate limits. Each lead keeps `reason` +
`discovered_via_record_id` — discovery itself is provenance-tracked. Running
discover → ingest-leads → discover repeatedly expands the graph one hop at a
time under your control.

## Compliance & responsible collection

**Protected attributes are redacted at ingest.** Free-text fields — bios,
headlines, roles, awards, locations — are screened before they become
queryable evidence, and material about someone's family, faith, health, age,
citizenship or gender identity is replaced with a named marker rather than
stored. The raw payload keeps the original, so provenance is intact and
nothing is silently rewritten; what changes is only what can be searched on.

The screening insists the mention be *about the person*. A researcher whose
stated interest is "how technology is affecting children and society" is
writing about a topic, not disclosing a family, and a colleague named
Christian is not disclosing a religion. `rip.cli audit-protected` scans what
is already stored and redacts in place with `--yes`.


- Official public APIs only; no scraping behind auth, CAPTCHAs, paywalls, or
  anti-bot measures — the base connector has no mechanisms for any of that.
- Rate limits honored (per-connector intervals + `Retry-After`).
- Only public professional data is collected; emails only when the person
  published them on their own profile. No sensitive-category data.
- Provenance retained for every claim, supporting deletion/audit requests
  (`DELETE person` cascade is a straightforward follow-up for GDPR-style
  erasure).

## Repository layout

```
backend/
  rip/
    db.py         engine/session, RIP_DATABASE_URL
    models.py     schema (person, source_record, evidence, edges, change_log, ...)
    normalize.py  NormalizedProfile IR + strong-key extraction
    resolution.py entity resolution strategies
    ingest.py     pipeline: upsert record → resolve → apply → change log
    nlq.py        natural-language query parsing + live discovery
    api.py        FastAPI read API; serves the built UI at /ui and /static
    cli.py        init-db / ingest / search-openalex / refresh / serve
    connectors/   github.py, openalex.py, exa.py, base.py (polite HTTP)
  scripts/        snapshot build, Postgres migration, benchmarks, nightly cron
  tests/          resolution + ingestion tests (fixture-based, no network)

web/              the React app — this is what you edit
  src/
    main.tsx      entry; applies the saved theme before first paint
    App.tsx       routes (hash-based) and the auth gate
    api/client.ts the one door to the backend; bearer auth, 401 handling
    types.ts      the shapes /v1 returns
    pages/        Search, Person, Shortlists, Review, Sources, Gate
    components/   Shell, Filters, ResultsTable, Network, EmptyState
    lib/          icons, brand links, the traced mark, formatting, hooks
    styles.css    design tokens, layout, motion
  vite.config.ts  builds into ../frontend, proxies /v1 in dev

frontend/         BUILD OUTPUT — generated by `npm run build`, do not edit

demo/             the product film and the script that records it
  film.py         the running order, driven over the DevTools protocol
  capture.py      the headless Chrome harness
  scenes.py       title cards, captions, typing, frame recording
  post.py         push-in, dissolves, and per-frame timing
  sound.py        the score, synthesised
  mix.py          cues the score to the scene marks
  seekr-demo.mp4  the cut
```

The two halves talk over HTTP and nothing else. The frontend is a React +
TypeScript single-page app built by Vite; the backend serves the built files
as static assets and never renders HTML.

`frontend/` is committed rather than ignored because the deploy target runs
Python only — it never runs npm — so the built bundle has to be in the
repository for `/ui` to work in production. Treat it as an artefact: edit
`web/`, run the build, commit both.

### Working on the frontend

```bash
cd web && npm install
```

Two ways to run it. For frontend work, Vite's dev server gives hot reload and
proxies `/v1` to the API on port 8000:

```bash
cd web && npm run dev
```

For everything else, build once and let the backend serve it — same URL,
same `/ui`, no second process:

```bash
cd web && npm run build
```

`npm run typecheck` runs TypeScript with no emit, which is what CI should
gate on.

## Deploying

**Handing this to someone who will deploy it? Start at
[deploy/README.md](deploy/README.md)** — the database decision, a local
Postgres stack to try first, and Kubernetes manifests.

## Deploying with Docker

One image serves the API and the UI on port 8000. The UI is built from `web/`
inside the image, so what ships is what the source says, not whatever bundle
happened to be committed.

```bash
docker build -t seekr .
```

```bash
docker run -d --name seekr -p 8000:8000 \
  -v seekr-data:/data \
  -e RIP_API_TOKEN=<a long random string> \
  --env-file .env \
  seekr
```

The UI is then at `http://localhost:8000/ui`.

**Set `RIP_API_TOKEN`.** Without it every `/v1` route is open, and these
routes return personal data about real people. The container starts either
way and says which mode it is in on the first line of its log — read it.

**`/data` is a volume, and it is the graph.** A container filesystem is
disposable; the SQLite file must not be. `RIP_DATABASE_URL` already points at
`/data/rip.db`, and the schema is created on first start, so an empty volume
is a valid starting point. To carry an existing graph in, take a consistent
snapshot rather than copying the file — a live database has un-checkpointed
WAL beside it, and copying the three files separately produces a torn read:

```bash
python -c "import sqlite3; sqlite3.connect('rip.db').execute('VACUUM INTO ?', ('seed.db',))"
```

Then place `seed.db` in the volume as `rip.db` before the first start.

**Secrets come from the environment, never the image.** `.env` and every
`*.db` are excluded by `.dockerignore`, so a build cannot bake in a token or
a copy of the graph. Pass them at run time with `--env-file` or `-e`.

The image runs as UID 10001, not root. On a Linux host using a bind mount
rather than a named volume, `chown -R 10001:10001 ./data` first, or the
process cannot write.

### Notes for a real deployment

- **One worker.** SQLite takes one writer, and `serve` enforces that. To run
  more than one process, move to Postgres via `RIP_DATABASE_URL` — the
  connection pool settings in `db.py` already switch on for server-backed
  engines.
- **Ingestion is not this container's job.** It serves. Run `ingest`,
  `refresh` and `deliver-webhooks` as separate jobs against the same volume
  or database.
- **Health.** `HEALTHCHECK` polls `/`, which needs no token and touches no
  tables, so it reports the process rather than the data.

## Running the full build

This is the version with every capability. One command:

```bash
.venv/bin/python -m rip.cli serve
```

It reads `.env` itself, prints what it is serving, and refuses to pretend:
if the database is read-only it says so, and if `RIP_API_TOKEN` is unset it
warns that the API is open. `--host 0.0.0.0` accepts connections from other
machines; `--workers N` needs Postgres, because SQLite does not take
concurrent writers.

What "full" means, against the read-only snapshot described below:

| | Full build | Bundled snapshot |
|---|---|---|
| People served | the whole graph (50,800+) | ~14,000 |
| Live search | finds people **and keeps them** | finds them, cannot store them |
| Corpus | grows with every query | fixed until redeployed |
| Raw payloads | kept, so parsers can improve without re-crawling | stripped |
| Background worker, webhooks | yes | no |
| Request time | unbounded | capped by the platform |

The graph is ~1.2 GB and grows. Any host that gives you a writable disk and
a long-running process will serve it; a serverless platform generally will
not.

### Postgres

SQLite is the default and is fine for one process. For several, or for a
graph you keep writing to while serving:

```bash
export RIP_DATABASE_URL=postgresql+psycopg://user:pass@host/seekr
.venv/bin/python -m rip.cli init-db
.venv/bin/python backend/scripts/migrate_to_postgres.py   # copies an existing SQLite graph
```

No code changes — every query in the codebase runs on both.

## Deployment as a read-only snapshot (optional)

A cut-down copy can be served from a platform with a read-only filesystem
(this repo carries a Vercel entrypoint at `api/index.py`). It is a demo of
the read API, not the product: the snapshot is capped at 100 MB, which is
roughly 14,000 people, and nothing found live can be kept.

```bash
.venv/bin/python backend/scripts/build_snapshot.py   # never copy rip.db by hand
```

`backend/scripts/build_snapshot.py` is the only supported way to build it. It
checkpoints the WAL, strips raw payloads and forces `journal_mode=DELETE` —
a WAL database **cannot be opened on a read-only filesystem**, so a
hand-copied `rip.db` produces a deployment where every `/v1` route returns
500 ("unable to open database file"). The script refuses to emit a WAL file
or a snapshot over the size limit.

Responses from such a deployment carry `"storage": "read-only"`, and the UI
says plainly that people found live are shown but not saved.

## Operations

**Never ingest inside the API server process.** The API is read-only and, in
production, reads a snapshot on a read-only filesystem. Ingestion runs from
cron (`backend/scripts/nightly_refresh.sh`) or a separate `rip.cli worker` process.
On SQLite that separation is what WAL mode makes safe; on Postgres it lets
you run several workers at once.

**Environment variables for the ingest host** (none are needed to *serve*):

| Variable | Why it matters |
|---|---|
| `GITHUB_TOKEN` | 60 → 5,000 requests/hour. Without it, enrichment stalls almost immediately |
| `SEMANTIC_SCHOLAR_API_KEY` | avoids shared-pool 429s |
| `OPENALEX_MAILTO` | polite pool: higher, more reliable limits |
| `RIP_LEAD_BATCH` | leads drained per nightly run (default 100) |
| `SEEKR_SEARCH_TTL_DAYS` | reuse a cached live search for this many days (default 7) |
| `RIP_DATABASE_URL` | defaults to `sqlite:///rip.db` |
| `RIP_API_TOKEN` | set on the *serving* side; makes `/v1` require a bearer token |

`rip.cli check-db` prints which of these are set, along with engine, journal
mode, and queue depths — run it first when something looks wrong.

**Batch sizing.** `RIP_LEAD_BATCH` defaults to 100 per nightly run. Enrichment
multiplies API calls per person (one lead can become 3–4 fetches), so without
`GITHUB_TOKEN` a tokenless run exhausts GitHub's 60/hour almost immediately —
every ingest command warns when credentials are missing. For large catch-up
runs, use `--no-enrich`; enrichment can be applied later by re-ingesting.
The worker backs off exponentially (to 15 min) when a whole batch fails,
which is what throttling looks like, and finishes its current batch before
exiting on Ctrl-C.

**Webhooks only fire when `deliver-webhooks` runs.** Nothing is pushed from
the API. Deliveries accumulate in an outbox until the CLI (invoked by the
nightly script) sends them, so a failing cron shows up as a growing backlog:
check `GET /v1/webhooks/health` or `rip.cli check-db`.

**Live discovery** is opt-in per request on `/v1/query`:

- `discover=false` (default) — local corpus only
- `discover=true` — additionally returns `discovery_suggestions` from live
  source searches; **nothing is ingested**
- `discover=queue` — same, and adds each suggestion to the discovery-lead
  queue for a worker to ingest later. Still no ingest inside the request

## Known limitations / roadmap

Done: ~~fuzzy resolution scans all persons~~ (blocked by org + name token),
~~no webhooks~~ (outbox + `deliver-webhooks`), ~~merge review needs a UI~~
(`/ui`), ~~single-source profiles~~ (enrichment chain).

Still open:

- `refresh` and the lead worker are single-process; parallel workers need
  Postgres (see [docs/POSTGRES.md](docs/POSTGRES.md)).
- Graph API is depth 1 only; deeper traversal would need a recursive CTE.
- Web connector reads one page per URL and does not follow site navigation —
  deliberate, but it means a profile split across several pages is partial.
- `discover=true` on `/v1/query` searches OpenAlex only; other sources have
  no author-search endpoint wired.
- Bulk ingest is single-threaded; throughput is bounded by resolution, not IO.
