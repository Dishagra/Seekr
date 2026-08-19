"""Natural-language query parsing for internal search.

Turns "distributed systems researchers at Google in London, top 10" into
structured filters. Deliberately NOT ranking: the parser extracts filter
constraints only, results stay in DB order, and the response is honest about
which terms were applied and which weren't.

The vocabulary is built from the live corpus (skill/interest values, org
names, locations) rather than hardcoded gazetteers, so it grows with the data.
"""

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Evidence, Organization, Person

STOPWORDS = {
    "a", "an", "and", "at", "expert", "experts", "engineer", "engineers", "find",
    "for", "from", "in", "me", "of", "on", "or", "people", "person", "profiles",
    "researcher", "researchers", "show", "someone", "specialist", "specialists",
    "the", "to", "who", "with", "working", "works", "developer", "developers",
    "scientist", "scientists", "top", "first", "list", "give", "get", "best",
}
SKILL_ATTRS = ("skill", "research_interest", "specialization")
FUZZY_VOCAB_THRESHOLD = 90.0
DEFAULT_LIMIT = 50
MAX_LIMIT = 500


@dataclass
class NLQuery:
    raw: str
    skills: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    name_terms: list[str] = field(default_factory=list)
    # terms that matched many vocabulary values: filtered by pattern rather
    # than by enumerating every match (which does not scale with the corpus)
    skill_patterns: list[str] = field(default_factory=list)
    limit: int = DEFAULT_LIMIT
    offset: int = 0
    unmatched_terms: list[str] = field(default_factory=list)


def _vocab(session: Session) -> tuple[dict, dict, dict]:
    """(skills, orgs, locations) lowercase -> canonical value, from live data."""
    skills = {
        v.lower(): v
        for (v,) in session.execute(
            select(Evidence.value).where(Evidence.attribute_type.in_(SKILL_ATTRS)).distinct()
        )
    }
    orgs = {
        v.lower(): v
        for (v,) in session.execute(select(Organization.name).distinct())
    }
    locations: dict[str, str] = {}
    for (loc,) in session.execute(
        select(Person.location).where(Person.location.isnot(None)).distinct()
    ):
        locations[loc.lower()] = loc
        # each comma part is matchable ("Berlin" from "Berlin, Germany")
        for part in loc.split(","):
            part = part.strip()
            if len(part) > 2:
                locations.setdefault(part.lower(), loc)
    return skills, orgs, locations


def _ngrams(tokens: list[str], max_n: int = 3):
    """Longest-first n-grams with their token spans."""
    for n in range(min(max_n, len(tokens)), 0, -1):
        for i in range(len(tokens) - n + 1):
            yield " ".join(tokens[i : i + n]), set(range(i, i + n))


def parse(session: Session, query: str) -> NLQuery:
    result = NLQuery(raw=query)

    # limit requires an explicit prefix — a bare number is never a limit
    limit_match = re.search(r"\b(?:top|first|show|list)\s+(\d{1,3})\b", query, re.I)
    if limit_match:
        result.limit = max(1, min(MAX_LIMIT, int(limit_match.group(1))))
    cleaned = re.sub(r"\b(?:top|first|show|list)\s+\d{1,3}\b", " ", query, flags=re.I)

    skills, orgs, locations = _vocab(session)
    tokens = [t for t in re.findall(r"[a-zA-Z0-9+#.'-]+", cleaned)]
    consumed: set[int] = set()

    for gram, span in _ngrams(tokens):
        if span & consumed:
            continue
        gram_l = gram.lower()
        if all(t.lower() in STOPWORDS for t in gram_l.split()):
            continue
        if gram_l in skills:
            result.skills.append(skills[gram_l])
            consumed |= span
        elif gram_l in orgs:
            result.organizations.append(orgs[gram_l])
            consumed |= span
        elif gram_l in locations:
            result.locations.append(locations[gram_l])
            consumed |= span
        elif len(gram_l) >= 5:
            # word-boundary containment: "machine learning" should match the
            # corpus value "Machine Learning in Materials Science". A few
            # matches are enumerated; many become a LIKE pattern, because
            # enumerating them breaks down as the corpus grows.
            pattern = re.compile(rf"\b{re.escape(gram_l)}\b")
            contained = [v for k, v in skills.items() if pattern.search(k)]
            if 0 < len(contained) <= 8:
                result.skills.extend(contained)
                consumed |= span
            elif contained:
                result.skill_patterns.append(gram_l)
                consumed |= span

    # fuzzy pass for near-miss skill terms ("kubernetes" vs "Kubernetes ops")
    for i, token in enumerate(tokens):
        if i in consumed or token.lower() in STOPWORDS or len(token) < 4:
            continue
        best = max(
            skills.items(),
            key=lambda kv: fuzz.ratio(token.lower(), kv[0]),
            default=None,
        )
        if best and fuzz.ratio(token.lower(), best[0]) >= FUZZY_VOCAB_THRESHOLD:
            result.skills.append(best[1])
            consumed.add(i)

    # leftovers: capitalized tokens are treated as name terms, rest unmatched
    for i, token in enumerate(tokens):
        if i in consumed or token.lower() in STOPWORDS:
            continue
        if token[:1].isupper():
            result.name_terms.append(token)
        else:
            result.unmatched_terms.append(token)

    result.skills = list(dict.fromkeys(result.skills))
    result.organizations = list(dict.fromkeys(result.organizations))
    result.locations = list(dict.fromkeys(result.locations))
    return result


def has_filters(parsed: NLQuery) -> bool:
    return bool(
        parsed.skills or parsed.skill_patterns or parsed.organizations
        or parsed.locations or parsed.name_terms
    )


def _filtered_stmt(parsed: NLQuery):
    """The filter query, without paging — shared by the count and the page."""
    from .models import Affiliation  # noqa: F401  (used below)

    from sqlalchemy import or_

    stmt = select(Person).where(Person.merged_into.is_(None))
    if parsed.skills or parsed.skill_patterns:
        clauses = []
        if parsed.skills:
            clauses.append(
                func.lower(Evidence.value).in_([s.lower() for s in parsed.skills])
            )
        for pat in parsed.skill_patterns:
            clauses.append(func.lower(Evidence.value).like(f"%{pat.lower()}%"))
        stmt = stmt.join(Evidence, Evidence.person_id == Person.id).where(
            Evidence.attribute_type.in_(SKILL_ATTRS), or_(*clauses)
        )
    if parsed.organizations:
        stmt = (
            stmt.join(Affiliation, Affiliation.person_id == Person.id)
            .join(Organization, Organization.id == Affiliation.organization_id)
            .where(func.lower(Organization.name).in_([o.lower() for o in parsed.organizations]))
        )
    if parsed.locations:
        stmt = stmt.where(or_(*[
            func.lower(Person.location).like(f"%{loc.split(',')[0].strip().lower()}%")
            for loc in parsed.locations
        ]))
    if parsed.name_terms:
        from sqlalchemy import String as SAString  # noqa: F401  (used below)

        for term in parsed.name_terms:
            pattern = f"%{term.lower()}%"
            stmt = stmt.where(
                func.lower(Person.canonical_name).like(pattern)
                | func.lower(func.cast(Person.aliases, SAString)).like(pattern)
            )
    return stmt


def count_matches(session: Session, parsed: NLQuery) -> int:
    """How many people match in total — not just how many this page returns."""
    if not has_filters(parsed):
        return 0
    inner = _filtered_stmt(parsed).with_only_columns(Person.id).distinct().subquery()
    return session.execute(select(func.count()).select_from(inner)).scalar_one()


def execute(session: Session, parsed: NLQuery) -> list[Person]:
    """Apply the parsed filters. No ranking: DB order, one page at a time.

    If NOTHING in the query matched the corpus vocabulary, return nothing.
    An unfiltered SELECT would hand back arbitrary people that look like
    answers to a question we could not actually answer.
    """
    if not has_filters(parsed):
        return []
    stmt = _filtered_stmt(parsed)
    # de-duplicate on id, not whole rows: Postgres cannot DISTINCT a JSON column
    ids = session.execute(
        stmt.with_only_columns(Person.id)
        .distinct()
        .limit(parsed.limit)
        .offset(parsed.offset)
    ).scalars().all()
    if not ids:
        return []
    rows = {p.id: p for p in session.execute(
        select(Person).where(Person.id.in_(ids))).scalars()}
    return [rows[i] for i in ids if i in rows]


def _search_openalex(query: str, limit: int) -> list[dict]:
    from .connectors import get_connector

    return [
        {
            "source": "openalex",
            "external_id": c["id"],
            "name": c.get("name"),
            "affiliation": c.get("affiliation"),
            "works_count": c.get("works_count"),
        }
        for c in get_connector("openalex").search_authors(query, limit=limit)
    ]


def _search_semanticscholar(query: str, limit: int) -> list[dict]:
    from .connectors import get_connector

    return [
        {
            "source": "semanticscholar",
            "external_id": c["id"],
            "name": c.get("name"),
            "affiliation": (c.get("affiliations") or [None])[0],
            "works_count": c.get("papers"),
        }
        for c in get_connector("semanticscholar").search_authors(query, limit=limit)
    ]


def _search_exa(query: str, limit: int) -> list[dict]:
    """People search over professional profiles. Costs money per call, so it
    runs only when the free scholarly sources found nothing."""
    import os

    from .connectors import get_connector

    if not os.environ.get("EXA_API_KEY"):
        return []
    return [
        {
            "source": "exa",
            "external_id": c["id"],
            "name": c.get("name"),
            "affiliation": c.get("affiliation"),
            "role": c.get("role"),
            "location": c.get("location"),
            "works_count": None,
        }
        for c in get_connector("exa").search_people(query, limit=limit)
    ]


def _search_dblp(query: str, limit: int) -> list[dict]:
    from .connectors import get_connector

    return [
        {
            "source": "dblp",
            "external_id": c["pid"],
            "name": c.get("name"),
            "affiliation": None,
            "works_count": None,
        }
        for c in get_connector("dblp").search_authors(query, limit=limit)
        if c.get("pid")
    ]


# tried in order; later sources only run if earlier ones found nothing useful
SUGGESTION_SEARCHERS = (
    ("openalex", _search_openalex),
    ("semanticscholar", _search_semanticscholar),
    ("dblp", _search_dblp),
    # paid, and the only source that reaches non-academic roles: tried last
    ("exa", _search_exa),
)
MIN_USEFUL_SUGGESTIONS = 3


def discovery_suggestions(parsed: NLQuery, limit: int = 10) -> list[dict]:
    """Live author search across sources for terms the local corpus lacks.

    Returns SUGGESTIONS only — nothing is ingested here. Sources are tried in
    order and later ones are skipped once enough candidates are found, so the
    common case still costs a single upstream call. A failing source is
    skipped rather than failing the query.
    """
    terms = parsed.unmatched_terms + parsed.name_terms
    if not terms:
        terms = parsed.skills[:1]
    query = " ".join(terms).strip()
    if not query:
        return []

    out: list[dict] = []
    for source, searcher in SUGGESTION_SEARCHERS:
        if len(out) >= MIN_USEFUL_SUGGESTIONS:
            break
        try:
            found = searcher(query, limit)
        except Exception:
            continue  # a throttled or unavailable source is not a query failure
        for item in found:
            if not item.get("external_id"):
                continue
            item["reason"] = f"live {source} author search for '{query}'"
            item["ingest_command"] = f"rip.cli ingest {source} {item['external_id']}"
            out.append(item)
    return out[: limit * 2]


def queue_suggestions(session: Session, suggestions: list[dict], query: str) -> int:
    """Add suggestions to the discovery-lead queue for a worker to ingest.

    Still no ingest inside the request: this only records intent, and the
    normal lead pipeline (rate limits, enrichment, resolution) applies when a
    worker picks it up.
    """
    from .discover import _add_lead
    from .models import DiscoveryLead, SourceRecord

    added = 0
    for item in suggestions:
        source, external_id = item.get("source"), item.get("external_id")
        if not source or not external_id:
            continue
        exists = session.execute(
            select(DiscoveryLead.id).where(
                DiscoveryLead.source == source, DiscoveryLead.identifier == external_id
            )
        ).first()
        already = session.execute(
            select(SourceRecord.id).where(
                SourceRecord.source == source, SourceRecord.external_id == external_id
            )
        ).first()
        if exists or already:
            continue
        session.add(
            DiscoveryLead(
                source=source,
                identifier=external_id,
                reason=f"queued from search '{query}': {item.get('name')}"[:1000],
            )
        )
        added += 1
    session.commit()
    return added
