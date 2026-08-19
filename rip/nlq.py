"""Natural-language query parsing for internal search.

Turns "distributed systems researchers at Google in London, top 10" into
structured filters. Deliberately NOT ranking: the parser extracts filter
constraints only, results stay in DB order, and the response is honest about
which terms were applied and which weren't.

The vocabulary is built from the live corpus (skill/interest values, org
names, locations) rather than hardcoded gazetteers, so it grows with the data.
"""

import logging
import os
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Evidence, Organization, Person

logger = logging.getLogger("rip.nlq")

# Words that describe what the searcher wants rather than what a person does.
# Without these, "strong in computer vision" matches the physics topic "Strong
# Light-Matter Interactions", and "at top conferences" matches "Conferences and
# Exhibitions Management". They are query grammar, not domain vocabulary.
STOPWORDS = {
    # articles, prepositions, conjunctions
    "a", "an", "and", "or", "the", "of", "in", "at", "on", "to", "from", "for",
    "with", "who", "whom", "whose", "that", "which", "both", "also", "than",
    "then", "into", "across", "about", "over", "under", "between", "not",
    "but", "as", "by", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "can", "could", "would", "should", "will",
    # asking for things
    "find", "show", "list", "give", "get", "need", "want", "looking", "look",
    "search", "me", "my", "i", "we", "us", "you", "please", "help", "few",
    "some", "any", "someone", "somebody", "people", "person", "persons",
    "profiles", "profile", "candidates", "folks", "individuals", "seem",
    "seems", "actually", "really", "ideally", "preferably", "unusually",
    "particularly", "especially", "strongest", "strong", "best", "top",
    "good", "great", "excellent", "solid", "leading", "notable", "prominent",
    # job words that are titles everywhere and topics nowhere
    "engineer", "engineers", "developer", "developers", "researcher",
    "researchers", "scientist", "scientists", "expert", "experts",
    "specialist", "specialists", "professional", "professionals",
    "practitioner", "practitioners", "contributor", "contributors",
    "maintainer", "maintainers", "founder", "founders", "manager", "managers",
    "designer", "designers", "architect", "architects", "lead", "leads",
    "senior", "junior", "staff", "principal", "head", "chief",
    # career/evidence talk
    "experience", "experienced", "expertise", "background", "worked", "works",
    "working", "work", "built", "build", "building", "contributed",
    "contributing", "contributions", "published", "publishing", "publication",
    "publications", "papers", "paper", "authored", "spoken", "speaking",
    "joined", "later", "previously", "currently", "current", "former",
    "years", "year", "public", "publicly", "presence", "evidence", "online",
    "portfolio", "profile", "show", "showing", "track", "record",
    "conferences", "conference", "venues", "companies", "company", "startup",
    "startups", "industry", "academia", "academic", "production", "real",
    "stuff", "scale", "large", "major", "popular", "significant",
    "substantial", "deploying", "deployed", "moved", "continue", "know",
    "knows", "understand", "understands", "spent", "time", "since",
    # generic product/role nouns: "product designers" must not reach
    # "Natural product bioactivities", and "tools" matches nothing useful
    "product", "products", "tools", "tool", "projects", "project", "platform",
    "platforms", "application", "applications", "apps", "app", "solutions",
    "services", "service", "technology", "technologies", "tech", "software",
    "systems" if False else "__unused__",
}
STOPWORDS.discard("__unused__")
SKILL_ATTRS = ("skill", "research_interest", "specialization")
# A GitHub bio reading "backend engineer, distributed systems" is real evidence
# of what someone does, even though no source emitted it as a tidy skill value.
TEXT_ATTRS = SKILL_ATTRS + ("bio", "role")
# Country names -> ISO codes. Reference data, not a guess about people: it
# lets "in India" become a real country filter even when no source recorded a
# city. Extend freely; unknown names simply stay unmatched.
COUNTRIES = {
    "india": "IN", "united states": "US", "usa": "US", "america": "US",
    "united kingdom": "GB", "uk": "GB", "britain": "GB", "england": "GB",
    "germany": "DE", "france": "FR", "canada": "CA", "china": "CN",
    "japan": "JP", "australia": "AU", "brazil": "BR", "spain": "ES",
    "italy": "IT", "netherlands": "NL", "switzerland": "CH", "sweden": "SE",
    "singapore": "SG", "israel": "IL", "south korea": "KR", "korea": "KR",
    "russia": "RU", "poland": "PL", "belgium": "BE", "austria": "AT",
    "denmark": "DK", "norway": "NO", "finland": "FI", "ireland": "IE",
    "portugal": "PT", "greece": "GR", "turkey": "TR", "mexico": "MX",
    "argentina": "AR", "chile": "CL", "south africa": "ZA", "egypt": "EG",
    "nigeria": "NG", "kenya": "KE", "pakistan": "PK", "bangladesh": "BD",
    "indonesia": "ID", "malaysia": "MY", "thailand": "TH", "vietnam": "VN",
    "philippines": "PH", "new zealand": "NZ", "czech republic": "CZ",
    "hungary": "HU", "romania": "RO", "ukraine": "UA", "saudi arabia": "SA",
    "united arab emirates": "AE", "uae": "AE", "iran": "IR", "taiwan": "TW",
    "hong kong": "HK", "colombia": "CO", "peru": "PE",
}
# "Indian researchers" means people in India, not the topic "Indian History".
DEMONYMS = {
    "indian": "IN", "american": "US", "british": "GB", "german": "DE",
    "french": "FR", "canadian": "CA", "chinese": "CN", "japanese": "JP",
    "australian": "AU", "brazilian": "BR", "spanish": "ES", "italian": "IT",
    "dutch": "NL", "swiss": "CH", "swedish": "SE", "israeli": "IL",
    "korean": "KR", "russian": "RU", "polish": "PL", "danish": "DK",
    "norwegian": "NO", "finnish": "FI", "irish": "IE", "portuguese": "PT",
    "greek": "GR", "turkish": "TR", "mexican": "MX", "nigerian": "NG",
    "kenyan": "KE", "pakistani": "PK", "singaporean": "SG",
}
# A word occurring in more than this share of vocabulary values is too generic
# to match on: "systems" appears in 147 topics, "robotics" in 7.
GENERIC_DF_RATIO = 0.01
GENERIC_DF_ABSOLUTE = 25
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
    countries: list[str] = field(default_factory=list)
    # terms that matched many vocabulary values: filtered by pattern rather
    # than by enumerating every match (which does not scale with the corpus)
    skill_patterns: list[str] = field(default_factory=list)
    # One entry per distinct concept the user asked for. Matches are ORed
    # WITHIN a group and ANDed ACROSS groups, so "robotics and computer
    # vision" means both, not either.
    skill_groups: list[dict] = field(default_factory=list)
    limit: int = DEFAULT_LIMIT
    offset: int = 0
    unmatched_terms: list[str] = field(default_factory=list)


def _text_evidence_exists(session: Session, term: str) -> bool:
    """Does any bio or job title mention this term?"""
    return session.execute(
        select(Evidence.id).where(
            Evidence.attribute_type.in_(("bio", "role")),
            func.lower(Evidence.value).like(f"%{term}%"),
        ).limit(1)
    ).first() is not None


# Acronyms carry the whole meaning of a query ("ML engineers at OpenAI") but are
# too short to survive the name/length guards, so they get dropped and the query
# silently becomes "engineers at OpenAI". Expand them to what the corpus calls
# them; if the expansion has no vocabulary match either, the term still drops.
ACRONYMS = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "nlp": "natural language",
    "cv": "computer vision",
    "llm": "large language model",
    "llms": "large language model",
    "ux": "user experience",
    "ui": "user interface",
    "hci": "human-computer interaction",
    "iot": "internet of things",
    "ar": "augmented reality",
    "vr": "virtual reality",
    "genai": "artificial intelligence",
    "rl": "reinforcement learning",
    "k8s": "kubernetes",
    "js": "javascript",
    "ts": "typescript",
    "ds": "data science",
    "bi": "business intelligence",
    "nlu": "natural language",
    "asr": "speech recognition",
    "cybersec": "cybersecurity",
    "infosec": "information security",
    "sre": "site reliability",
    "qa": "quality assurance",
}


def _token_frequency(skills: dict) -> dict:
    """How many vocabulary values contain each word — a genericness measure."""
    from collections import Counter

    df: Counter = Counter()
    for key in skills:
        for word in set(re.findall(r"[a-z0-9]+", key)):
            df[word] += 1
    return df


def _is_generic(term: str, df: dict, vocab_size: int) -> bool:
    """Would matching this term sweep in unrelated topics?"""
    words = term.split()
    if len(words) > 1:
        return False  # a phrase is specific enough to match on
    n = df.get(term, 0)
    return n > max(GENERIC_DF_ABSOLUTE, vocab_size * GENERIC_DF_RATIO)


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
    df = _token_frequency(skills)
    vocab_size = max(1, len(skills))
    tokens = [t for t in re.findall(r"[a-zA-Z0-9+#.'-]+", cleaned)]
    consumed: set[int] = set()

    for gram, span in _ngrams(tokens):
        if span & consumed:
            continue
        gram_l = gram.lower()
        parts = gram_l.split()
        if all(t in STOPWORDS for t in parts):
            continue
        # A phrase that opens or closes on a filler word ("in India",
        # "learning in") is not a real term — it would match a skill that
        # merely contains the preposition. The tighter n-gram covers the
        # meaningful part, so skip this one.
        if len(parts) > 1 and (parts[0] in STOPWORDS or parts[-1] in STOPWORDS):
            continue
        if gram_l in skills:
            result.skill_groups.append({"term": gram, "values": [skills[gram_l]]})
            consumed |= span
        elif gram_l in orgs:
            result.organizations.append(orgs[gram_l])
            consumed |= span
        elif gram_l in COUNTRIES:
            result.countries.append(COUNTRIES[gram_l])
            consumed |= span
        elif gram_l in DEMONYMS:
            # "Indian researchers" is a place, not the topic "Indian History"
            result.countries.append(DEMONYMS[gram_l])
            consumed |= span
        elif gram_l in locations:
            result.locations.append(locations[gram_l])
            consumed |= span
        elif gram_l in ACRONYMS and ACRONYMS[gram_l] in skills:
            result.skill_groups.append({"term": gram, "values": [skills[ACRONYMS[gram_l]]]})
            consumed |= span
        elif gram_l in ACRONYMS:
            expansion = ACRONYMS[gram_l]
            pattern = re.compile(rf"\b{re.escape(expansion)}\b")
            contained = [v for k, v in skills.items() if pattern.search(k)]
            if contained:
                result.skill_groups.append({"term": gram, "values": contained})
                consumed |= span
        elif len(gram_l) >= 5 and not _is_generic(gram_l, df, vocab_size):
            # Word-boundary containment: "computer vision" should reach
            # "Computer Vision and Image Processing". Generic words are
            # excluded above, or "building" would match building materials.
            pattern = re.compile(rf"\b{re.escape(gram_l)}\b")
            contained = [v for k, v in skills.items() if pattern.search(k)]
            group = {"term": gram}
            if not contained:
                # no topic matches, but a bio or job title might say it
                if _text_evidence_exists(session, gram_l):
                    result.skill_groups.append(group)
                    consumed |= span
                    continue
                exact = any(
                    t in skills or t in orgs or t in locations or t in COUNTRIES
                    for t in parts
                )
                if len(parts) > 1 and not exact:
                    # A phrase the corpus does not know must not be split into
                    # its words: "computer vision" has no matching topic, and
                    # the bare word "computer" reaches EEG and Brain-Computer
                    # Interfaces. Consume the span so the parts cannot match by
                    # mere containment. Words that are exact vocabulary in their
                    # own right ("Python" in "Python developers") are spared.
                    consumed |= span
                    # still tell the caller the phrase was dropped
                    result.unmatched_terms.append(gram)
                continue
            if len(contained) <= 12:
                group["values"] = contained
            else:
                group["pattern"] = gram_l
            result.skill_groups.append(group)
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
            result.skill_groups.append({"term": token, "values": [best[1]]})
            consumed.add(i)

    # Leftovers. A capitalised word is NOT automatically a person's name:
    # treating "Hyderabad" as one silently guarantees zero results. Only apply
    # a name filter when somebody in the corpus actually has that name;
    # otherwise report the term as unapplied and let the caller see why.
    for i, token in enumerate(tokens):
        if i in consumed or token.lower() in STOPWORDS:
            continue
        if token[:1].isupper() and _name_exists(session, token):
            result.name_terms.append(token)
        else:
            result.unmatched_terms.append(token)

    # flat views, kept so the API response and existing callers stay simple
    result.skills = list(dict.fromkeys(
        v for g in result.skill_groups for v in g.get("values", [])))
    result.skill_patterns = list(dict.fromkeys(
        g["pattern"] for g in result.skill_groups if g.get("pattern")))
    result.organizations = list(dict.fromkeys(result.organizations))
    result.locations = list(dict.fromkeys(result.locations))
    result.countries = list(dict.fromkeys(result.countries))
    return result


def _name_clauses(column, token: str):
    """Word-boundary name match, since SQLite has no regex.

    A substring test makes "AI" match "A. Aijaz" and "Suaide" — 2,027 people
    in this corpus — so a query about AI silently becomes a query about names.
    """
    t = token.lower()
    return (
        func.lower(column) == t,
        func.lower(column).like(f"{t} %"),
        func.lower(column).like(f"% {t}"),
        func.lower(column).like(f"% {t} %"),
        func.lower(column).like(f"{t}, %"),
        func.lower(column).like(f"% {t}, %"),
    )


def _looks_like_a_name(token: str) -> bool:
    """Acronyms are technologies, not surnames: AI, ML, UX, API, SQL."""
    return len(token) >= 4 and not token.isupper()


def _name_exists(session: Session, token: str) -> bool:
    """Does anyone in the corpus actually carry this word as part of a name?"""
    from sqlalchemy import or_

    if not _looks_like_a_name(token):
        return False
    return session.execute(
        select(Person.id).where(
            or_(*_name_clauses(Person.canonical_name, token)),
            Person.merged_into.is_(None),
        ).limit(1)
    ).first() is not None


def has_filters(parsed: NLQuery) -> bool:
    return bool(
        parsed.skill_groups or parsed.organizations
        or parsed.locations or parsed.name_terms or parsed.countries
    )


def _filtered_stmt(parsed: NLQuery):
    """The filter query, without paging — shared by the count and the page."""
    from .models import Affiliation  # noqa: F401  (used below)

    from sqlalchemy import or_

    from sqlalchemy import and_, exists as sa_exists

    stmt = select(Person).where(Person.merged_into.is_(None))
    # One EXISTS per concept: a person must satisfy EVERY concept asked for,
    # while any of that concept's matching topics will do. ORing everything
    # together instead would turn "robotics and computer vision" into "either".
    for group in parsed.skill_groups:
        clauses = []
        if group.get("values"):
            clauses.append(and_(
                Evidence.attribute_type.in_(SKILL_ATTRS),
                func.lower(Evidence.value).in_([v.lower() for v in group["values"]]),
            ))
        if group.get("pattern"):
            clauses.append(and_(
                Evidence.attribute_type.in_(SKILL_ATTRS),
                func.lower(Evidence.value).like(f"%{group['pattern'].lower()}%"),
            ))
        # the raw term as written, against free text (bio, job title)
        term = (group.get("term") or "").lower()
        if len(term) >= 4:
            clauses.append(and_(
                Evidence.attribute_type.in_(("bio", "role")),
                func.lower(Evidence.value).like(f"%{term}%"),
            ))
        if not clauses:
            continue
        stmt = stmt.where(sa_exists().where(and_(
            Evidence.person_id == Person.id, or_(*clauses),
        )))
    if parsed.organizations:
        stmt = (
            stmt.join(Affiliation, Affiliation.person_id == Person.id)
            .join(Organization, Organization.id == Affiliation.organization_id)
            .where(func.lower(Organization.name).in_([o.lower() for o in parsed.organizations]))
        )
    if parsed.countries:
        stmt = stmt.where(func.upper(Person.country).in_(parsed.countries))
    if parsed.locations:
        stmt = stmt.where(or_(*[
            func.lower(Person.location).like(f"%{loc.split(',')[0].strip().lower()}%")
            for loc in parsed.locations
        ]))
    if parsed.name_terms:
        from sqlalchemy import String as SAString  # noqa: F401  (used below)

        for term in parsed.name_terms:
            stmt = stmt.where(or_(
                *_name_clauses(Person.canonical_name, term),
                func.lower(func.cast(Person.aliases, SAString)).like(f"%\"{term.lower()}%"),
            ))
    return stmt


def count_matches(session: Session, parsed: NLQuery) -> int:
    """How many people match in total — not just how many this page returns."""
    if not has_filters(parsed):
        return 0
    inner = _filtered_stmt(parsed).with_only_columns(Person.id).distinct().subquery()
    return session.execute(select(func.count()).select_from(inner)).scalar_one()


FILTER_GROUPS = ("skill_groups", "organizations", "locations", "countries", "name_terms")


def diagnose_empty(session: Session, parsed: NLQuery) -> dict | None:
    """When filters combine to nothing, say which one is responsible.

    Every filter can be individually reasonable while the intersection is
    empty — "growth" matches an economics topic, "Zomato" matches employers,
    and nobody is both. Reporting a bare 0 makes that look like a fault.
    """
    from dataclasses import replace

    active = [g for g in FILTER_GROUPS if getattr(parsed, g)]
    if len(active) < 2:
        return None
    for group in active:
        relaxed = replace(parsed)
        setattr(relaxed, group, [])
        if not has_filters(relaxed):
            continue
        n = count_matches(session, relaxed)
        if n:
            dropped = getattr(parsed, group)
            if group == "skill_groups":
                dropped = [g["term"] for g in dropped]
            return {
                "filter": group,
                "values": list(dropped),
                "would_match": n,
                "message": (
                    f"No one matches every filter at once. Dropping "
                    f"{group.replace('_', ' ')} ({', '.join(map(str, dropped))}) "
                    f"would return {n:,}."
                ),
            }
    return None


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

    conn = get_connector("openalex")
    # Topic first: "computer vision researchers" must find people who publish
    # on computer vision, not people whose surname matches the words.
    candidates = [c for c in conn.search_authors_by_topic(query, limit=limit)
                  if _looks_like_a_person(c.get("name"))]
    if not candidates:
        candidates = [c for c in conn.search_authors(query, limit=limit)
                      if _looks_like_a_person(c.get("name"))]
    return [
        {
            "source": "openalex",
            "external_id": c["id"],
            "name": c.get("name"),
            "affiliation": c.get("affiliation"),
            "works_count": c.get("works_count"),
        }
        for c in candidates
    ]


def _old_search_openalex(query: str, limit: int) -> list[dict]:
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
            # the full person payload we already paid for — ingesting it costs
            # nothing more, and means this query is answered locally next time
            "_raw": c.get("raw"),
            "_connector": "exa",
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
# (name, fn, uses_full_query). Author-name lookups want just the leftover
# terms; a semantic people search wants the whole question, because stripping
# "engineers at ... in Bengaluru" throws away the very context it matches on.
SUGGESTION_SEARCHERS = (
    ("openalex", _search_openalex, True),
    ("semanticscholar", _search_semanticscholar, False),
    ("dblp", _search_dblp, False),
    # paid, and the only source that reaches non-academic roles: tried last
    ("exa", _search_exa, True),
)
MIN_USEFUL_SUGGESTIONS = 3


# A cached live search is reused for this long before the provider is asked
# again. Short enough that job changes surface within a week; long enough that
# repeating a search costs nothing.
SEARCH_TTL_DAYS = int(os.environ.get("SEEKR_SEARCH_TTL_DAYS", "7"))


def _norm_query(q: str) -> str:
    return " ".join(sorted(re.findall(r"[a-z0-9]+", q.lower())))[:512]


def _cache_lookup(session: Session, provider: str, query: str):
    """The cache row for this query if it is still fresh, else None."""
    from datetime import datetime, timedelta, timezone

    from .models import SearchCache

    row = session.execute(
        select(SearchCache).where(
            SearchCache.provider == provider,
            SearchCache.query_norm == _norm_query(query),
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    age = datetime.now(timezone.utc) - row.ran_at.replace(tzinfo=timezone.utc)
    return row if age < timedelta(days=SEARCH_TTL_DAYS) else None


def _cache_record(session: Session, provider: str, query: str, found: int, stored: int) -> None:
    from datetime import datetime, timezone

    from .models import SearchCache

    row = session.execute(
        select(SearchCache).where(
            SearchCache.provider == provider,
            SearchCache.query_norm == _norm_query(query),
        )
    ).scalar_one_or_none()
    if row is None:
        row = SearchCache(provider=provider, query_norm=_norm_query(query), query_raw=query[:512])
        session.add(row)
    row.result_count, row.stored_count = found, stored
    row.ran_at = datetime.now(timezone.utc)
    session.commit()


# Sources whose full-profile fetch is a free public API, so a live search can
# be turned into real stored people without spending anything.
FREE_FETCH_SOURCES = ("openalex", "semanticscholar", "dblp")

# Scholarly indexes carry entity records that are not people: conferences,
# labs, societies, even "Computer Vision Syndrome". Ingesting them as persons
# pollutes the graph, so they are rejected before any fetch.
NOT_A_PERSON = re.compile(
    r"\b(foundation|conference|workshop|symposium|proceedings|society|institute"
    r"|laborator(y|ies)|university|college|committee|association|consortium"
    r"|group|centre|center|department|journal|press|syndrome|corporation|inc"
    r"|ltd|llc|gmbh|team|proj(ect)?|proceedings)\b",
    re.IGNORECASE,
)


def _looks_like_a_person(name: str | None) -> bool:
    """Filter index entities out of author search results."""
    if not name or len(name) > 60:
        return False
    if NOT_A_PERSON.search(name):
        return False
    # a person's name is a couple of words, not a sentence
    return 1 <= len(name.split()) <= 6
MAX_FREE_FETCHES = 10
# concurrent profile fetches: enough to hide latency, gentle on the source
FETCH_WORKERS = 5


def persist_suggestions(session: Session, suggestions: list[dict]) -> int:
    """Ingest live results, so a query the corpus could not answer grows it.

    Two kinds of result arrive here. Exa returns the whole person record in the
    search response — already bought, so storing it costs nothing. The free
    scholarly sources return only an identifier, so the profile has to be
    fetched; that request is free, and bounded per query.

    Fetches run concurrently because they are independent HTTP calls and doing
    them one at a time put a live query near 30 seconds. Ingest stays on this
    thread: a SQLAlchemy session is not safe to share.
    """
    from concurrent.futures import ThreadPoolExecutor

    from .connectors import get_connector
    from .ingest import ingest_profile

    def _keep(item: dict, profile) -> None:
        nonlocal stored
        try:
            person = ingest_profile(session, profile)
            item["stored"] = True
            item["person_id"] = str(person.id)
            stored += 1
        except Exception as exc:
            # surfaced on the item so a caller can see the record was found
            # but not kept, rather than it vanishing silently
            item["stored"] = False
            item["store_error"] = f"{type(exc).__name__}: {exc}"
            logger.warning("could not persist %s result: %s", item.get("source"), exc)
            session.rollback()

    stored = 0
    to_fetch: list[dict] = []
    for item in suggestions:
        raw, source = item.get("_raw"), item.get("_connector")
        if raw and source:
            try:
                _keep(item, get_connector(source).normalize(raw))
            except Exception as exc:
                item["stored"] = False
                item["store_error"] = f"{type(exc).__name__}: {exc}"
            continue
        if item.get("source") in FREE_FETCH_SOURCES and item.get("external_id"):
            if len(to_fetch) < MAX_FREE_FETCHES:
                to_fetch.append(item)

    if to_fetch:
        def _pull(item: dict):
            try:
                return item, get_connector(item["source"]).fetch(item["external_id"]), None
            except Exception as exc:
                return item, None, exc

        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            for item, profile, exc in pool.map(_pull, to_fetch):
                if exc is not None:
                    item["stored"] = False
                    item["store_error"] = f"{type(exc).__name__}: {exc}"
                    logger.warning("could not fetch %s result: %s", item.get("source"), exc)
                    continue
                _keep(item, profile)
    return stored


def discovery_suggestions(
    session: Session | None = None, parsed: NLQuery = None, limit: int = 10
) -> list[dict]:
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
    # stable across vocabulary changes, unlike the derived `query`
    cache_key = (parsed.raw or query).strip()

    out: list[dict] = []
    for source, searcher, uses_full_query in SUGGESTION_SEARCHERS:
        if len(out) >= MIN_USEFUL_SUGGESTIONS:
            break
        # Already bought this answer recently? The people are in the graph, so
        # do not pay for it again. Keyed on the USER'S query, not the derived
        # search string: once new people are stored the residual string
        # changes, and keying on that would bill for the same request twice.
        if session is not None and _cache_lookup(session, source, cache_key):
            continue
        try:
            found = searcher(cache_key if uses_full_query else query, limit)
        except Exception:
            continue  # a throttled or unavailable source is not a query failure
        keep = []
        for item in found:
            if not item.get("external_id"):
                continue
            item["reason"] = (
                f"live {source} search for "
                f"'{cache_key if uses_full_query else query}'"
            )
            item["ingest_command"] = f"rip.cli ingest {source} {item['external_id']}"
            keep.append(item)
        stored = persist_suggestions(session, keep) if session is not None else 0
        if session is not None:
            _cache_record(session, source, cache_key, len(keep), stored)
        out.extend(keep)
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
