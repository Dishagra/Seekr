from rip.ingest import ingest_profile
from rip.nlq import execute, parse
from rip.normalize import EvidenceItem, OrgAffiliation
from tests.test_resolution import make_profile


def seed(session):
    ingest_profile(
        session,
        make_profile(
            name="Ada Example",
            location="Toronto, Canada",
            organizations=[OrgAffiliation(name="Acme Labs", is_current=True)],
            evidence=[
                EvidenceItem(attribute_type="skill", value="Rust"),
                EvidenceItem(attribute_type="research_interest", value="Distributed Systems"),
            ],
        ),
    )
    ingest_profile(
        session,
        make_profile(
            external_id="other",
            url="https://github.com/other",
            raw={"login": "other"},
            name="Grace Sample",
            usernames=["github:other"],
            location="Berlin, Germany",
            organizations=[OrgAffiliation(name="Globex University", relation="studied_at")],
            evidence=[EvidenceItem(attribute_type="skill", value="Python")],
        ),
    )


def test_vocab_driven_parse(session):
    seed(session)
    parsed = parse(session, "distributed systems experts at Acme Labs in Toronto, top 5")
    assert parsed.skills == ["Distributed Systems"]
    assert parsed.organizations == ["Acme Labs"]
    assert parsed.locations == ["Toronto, Canada"]
    assert parsed.limit == 5
    assert parsed.unmatched_terms == []


def test_bare_number_is_not_limit(session):
    seed(session)
    # growthOS bug regression: "10 years" must not become limit=10
    parsed = parse(session, "rust with 10 years experience")
    assert parsed.limit == 50  # DEFAULT_LIMIT, not the bare "10"
    assert parsed.skills == ["Rust"]
    assert "10" in parsed.unmatched_terms or "years" in parsed.unmatched_terms


def test_execute_applies_all_filters(session):
    seed(session)
    results = execute(session, parse(session, "rust at Acme Labs"))
    assert [p.canonical_name for p in results] == ["Ada Example"]
    # unknown skill applied as nothing -> honest unmatched, no accidental filter
    parsed = parse(session, "quantum basketweaving experts")
    assert parsed.skills == []
    assert "quantum" in parsed.unmatched_terms or "basketweaving" in parsed.unmatched_terms


def test_name_term_filter(session):
    seed(session)
    results = execute(session, parse(session, "find Grace"))
    assert [p.canonical_name for p in results] == ["Grace Sample"]


def test_no_ranking_db_order(session):
    seed(session)
    # no scores anywhere in the parse result
    parsed = parse(session, "python")
    assert not hasattr(parsed, "score")
    results = execute(session, parsed)
    assert [p.canonical_name for p in results] == ["Grace Sample"]


def test_containment_matches_longer_corpus_values(session):
    seed(session)
    ingest_profile(
        session,
        make_profile(
            external_id="third", url="https://github.com/third", raw={"login": "third"},
            name="Ng Trailblazer", usernames=["github:third"],
            evidence=[EvidenceItem(attribute_type="research_interest",
                                   value="Neural Networks and Applications")],
        ),
    )
    parsed = parse(session, "neural networks researchers")
    assert parsed.skills == ["Neural Networks and Applications"]
    results = execute(session, parsed)
    assert [p.canonical_name for p in results] == ["Ng Trailblazer"]


def test_discovery_suggestions_are_not_results(session, monkeypatch):
    """Phase 4: discover=true adds suggestions, never auto-ingests."""
    from rip.api import nl_query
    from rip.models import Person, SourceRecord

    class FakeOpenAlex:
        def search_authors(self, name, limit=10):
            return [{"id": "A999", "name": "Marie Curie", "works_count": 12,
                     "affiliation": "Sorbonne", "cited_by": 3}]

    monkeypatch.setattr("rip.connectors.get_connector", lambda s: FakeOpenAlex())
    before_persons = session.query(Person).count()
    before_records = session.query(SourceRecord).count()

    resp = nl_query(q="radioactivity pioneers", discover="true", db=session)
    assert resp["count"] == 0
    assert resp["discover_available"] is True
    suggestions = resp["discovery_suggestions"]
    assert suggestions[0]["external_id"] == "A999"
    assert "ingest openalex A999" in suggestions[0]["ingest_command"]
    # nothing entered the graph
    assert session.query(Person).count() == before_persons
    assert session.query(SourceRecord).count() == before_records
    # no ranking leaked into the response
    assert "score" not in str(resp)


def test_discover_defaults_off(session, monkeypatch):
    """Live search is opt-in: default off over HTTP, and off means no fetch."""
    import inspect

    from rip.api import app, nl_query

    # declared default (what an HTTP caller gets without the param)
    assert inspect.signature(nl_query).parameters["discover"].default.default == "false"
    schema = app.openapi()["paths"]["/v1/query"]["get"]["parameters"]
    discover_param = next(p for p in schema if p["name"] == "discover")
    assert discover_param["schema"]["default"] == "false"
    assert discover_param["required"] is False

    def boom(source):
        raise AssertionError("live search must not run when discover=false")

    monkeypatch.setattr("rip.connectors.get_connector", boom)
    for off in ("false", "no", ""):
        resp = nl_query(q="radioactivity pioneers", discover=off, db=session)
        assert "discovery_suggestions" not in resp
        assert "queued_leads" not in resp


class _FakeSearcher:
    """Stands in for a connector's search_authors, recording calls."""

    def __init__(self, results, calls, name, fail=False):
        self._results, self._calls, self._name, self._fail = results, calls, name, fail

    def search_authors(self, query, limit=10):
        self._calls.append(self._name)
        if self._fail:
            raise RuntimeError(f"{self._name} unavailable")
        return self._results


def _patch_sources(monkeypatch, openalex=None, s2=None, dblp=None, fail=()):
    calls = []
    registry = {
        "openalex": _FakeSearcher(openalex or [], calls, "openalex", "openalex" in fail),
        "semanticscholar": _FakeSearcher(s2 or [], calls, "semanticscholar", "semanticscholar" in fail),
        "dblp": _FakeSearcher(dblp or [], calls, "dblp", "dblp" in fail),
    }
    monkeypatch.setattr("rip.connectors.get_connector", lambda s: registry[s])
    monkeypatch.setattr("rip.nlq.SUGGESTION_SEARCHERS", tuple(
        (n, f, u) for (n, f, u) in __import__("rip.nlq", fromlist=["x"]).SUGGESTION_SEARCHERS
        if n != "exa"))
    return calls


def test_suggestions_fall_through_to_other_sources(session, monkeypatch):
    """OpenAlex finding nothing must not end the search."""
    from rip.api import nl_query

    calls = _patch_sources(
        monkeypatch,
        openalex=[],
        s2=[{"id": "S1", "name": "Ada S2", "affiliations": ["MIT"], "papers": 9}],
        dblp=[{"pid": "12/345", "name": "Ada dblp"}],
    )
    resp = nl_query(q="quantum basketweaving", discover="true", db=session)
    sources = {s["source"] for s in resp["discovery_suggestions"]}
    assert sources == {"semanticscholar", "dblp"}
    assert calls == ["openalex", "semanticscholar", "dblp"]
    s2_hit = next(s for s in resp["discovery_suggestions"] if s["source"] == "semanticscholar")
    assert s2_hit["affiliation"] == "MIT"
    assert "ingest semanticscholar S1" in s2_hit["ingest_command"]


def test_later_sources_skipped_once_enough_found(session, monkeypatch):
    from rip.api import nl_query

    plenty = [{"id": f"A{i}", "name": f"P{i}"} for i in range(5)]
    calls = _patch_sources(monkeypatch, openalex=plenty)
    nl_query(q="quantum basketweaving", discover="true", db=session)
    assert calls == ["openalex"]  # no needless upstream calls


def test_failing_source_does_not_fail_the_query(session, monkeypatch):
    from rip.api import nl_query

    _patch_sources(
        monkeypatch,
        s2=[{"id": "S1", "name": "Ada S2"}],
        fail=("openalex",),
    )
    resp = nl_query(q="quantum basketweaving", discover="true", db=session)
    assert [s["source"] for s in resp["discovery_suggestions"]] == ["semanticscholar"]


def test_discover_queue_adds_leads_but_never_ingests(session, monkeypatch):
    from rip.api import nl_query
    from rip.models import DiscoveryLead, Person, SourceRecord

    _patch_sources(monkeypatch, openalex=[{"id": "A999", "name": "Marie Curie"}])
    before = (session.query(Person).count(), session.query(SourceRecord).count())
    resp = nl_query(q="radioactivity pioneers", discover="queue", db=session)

    assert resp["queued_leads"] == 1
    lead = session.query(DiscoveryLead).filter_by(identifier="A999").one()
    assert lead.status == "pending" and lead.source == "openalex"
    assert "radioactivity pioneers" in lead.reason
    # nothing entered the graph during the request
    assert (session.query(Person).count(), session.query(SourceRecord).count()) == before


def test_queue_is_idempotent_and_skips_known_records(session, monkeypatch):
    from rip.api import nl_query
    from rip.models import DiscoveryLead

    _patch_sources(monkeypatch, openalex=[{"id": "A999", "name": "Marie Curie"}])
    nl_query(q="radioactivity pioneers", discover="queue", db=session)
    resp = nl_query(q="radioactivity pioneers", discover="queue", db=session)
    assert resp["queued_leads"] == 0
    assert session.query(DiscoveryLead).filter_by(identifier="A999").count() == 1


def test_unmatched_query_returns_nothing_not_everything(session):
    """Regression: a query matching no vocabulary must not return arbitrary rows.

    "top program managers at oyo" against an academic corpus previously
    applied zero filters and then returned the first 25 people in the table,
    which reads as a wrong answer rather than no answer.
    """
    from rip.api import nl_query
    from rip.nlq import has_filters

    seed(session)
    parsed = parse(session, "top program managers at oyo")
    assert not has_filters(parsed)
    assert execute(session, parsed) == []

    resp = nl_query(q="top program managers at oyo", discover="false", db=session)
    assert resp["count"] == 0
    assert resp["results"] == []
    assert resp["matched_nothing"] is True
    assert "no filter could be applied" in resp["explanation"].lower()


def test_partial_match_still_filters(session):
    """One recognised term is enough; only a total miss returns nothing."""
    from rip.api import nl_query
    from rip.nlq import has_filters

    seed(session)
    parsed = parse(session, "rust program managers at oyo")
    assert has_filters(parsed)  # "rust" matched
    resp = nl_query(q="rust program managers at oyo", discover="false", db=session)
    assert resp["matched_nothing"] is False
    assert resp["count"] == 1
    assert resp["results"][0]["canonical_name"] == "Ada Example"


def test_queue_lead_endpoint(session):
    """UI live-search 'Queue' button: records intent, never ingests."""
    from fastapi import HTTPException
    from rip.api import queue_lead
    from rip.models import DiscoveryLead, Person

    before = session.query(Person).count()
    r = queue_lead({"source": "openalex", "external_id": "A123"}, db=session)
    assert r["status"] == "queued"
    lead = session.query(DiscoveryLead).filter_by(identifier="A123").one()
    assert lead.status == "pending"
    assert session.query(Person).count() == before  # nothing ingested

    # idempotent
    assert queue_lead({"source": "openalex", "external_id": "A123"}, db=session)["status"] == "already_queued"

    for bad in ({}, {"source": "openalex"}, {"source": "nope", "external_id": "x"}):
        try:
            queue_lead(bad, db=session)
            raise AssertionError(f"should have rejected {bad}")
        except HTTPException as exc:
            assert exc.status_code == 422


def test_queue_lead_detects_already_ingested(session):
    from rip.api import queue_lead
    from tests.test_ingest import github_profile

    ingest_profile(session, github_profile())
    r = queue_lead({"source": "github", "external_id": "jdoe"}, db=session)
    assert r["status"] == "already_ingested"


def _filters(session, **kw):
    from rip.api import list_persons

    base = dict(q=None, skill=None, organization=None, current_organization=None,
                education=None, role=None, country=None, location=None, source=None,
                technology=None, min_publications=None, min_citations=None,
                min_sources=None, active_since=None, updated_since=None,
                has_cv=None, has_email=None, sort="relevance", limit=50, offset=0,
                db=session)
    base.update(kw)
    return list_persons(**base)


def test_every_filter_narrows_correctly(session):
    from rip.normalize import EvidenceItem, OrgAffiliation, ProjectData, PublicationData

    ingest_profile(
        session,
        make_profile(
            name="Asha Rao", location="Bengaluru, India", country="IN",
            organizations=[
                OrgAffiliation(name="Acme Labs", role="Principal Engineer", is_current=True),
                OrgAffiliation(name="IIT Madras", relation="studied_at"),
            ],
            evidence=[EvidenceItem(attribute_type="skill", value="Distributed Systems")],
            projects=[ProjectData(name="fastdb", url="https://x/1", technologies=["Rust"])],
            publications=[PublicationData(title="P1", external_id="d1", doi="d1",
                                          published_date="2024", citations=120)],
        ),
    )
    ingest_profile(
        session,
        make_profile(
            source="dblp", external_id="9/9", url="https://dblp.org/pid/9/9",
            raw={"name": "Ben Cole"}, name="Ben Cole", usernames=[],
            location="Berlin, Germany", country="DE",
            organizations=[OrgAffiliation(name="Globex", is_current=True)],
        ),
    )

    assert _filters(session, country="IN")["total_matches"] == 1
    assert _filters(session, country="in")["total_matches"] == 1  # case-insensitive
    assert _filters(session, location="berlin")["total_matches"] == 1
    assert _filters(session, organization="Acme")["total_matches"] == 1
    assert _filters(session, current_organization="Globex")["total_matches"] == 1
    assert _filters(session, education="IIT")["total_matches"] == 1
    assert _filters(session, role="Principal")["total_matches"] == 1
    assert _filters(session, skill="distributed")["total_matches"] == 1
    assert _filters(session, technology="rust")["total_matches"] == 1
    assert _filters(session, source="dblp")["total_matches"] == 1
    assert _filters(session, min_publications=1)["total_matches"] == 1
    assert _filters(session, min_citations=100)["total_matches"] == 1
    assert _filters(session, min_citations=500)["total_matches"] == 0
    assert _filters(session, active_since="2020")["total_matches"] == 1
    assert _filters(session, active_since="2030")["total_matches"] == 0
    assert _filters(session, has_cv=False)["total_matches"] == 2
    assert _filters(session, has_cv=True)["total_matches"] == 0
    # combining filters is AND, not OR
    assert _filters(session, country="IN", skill="distributed")["total_matches"] == 1
    assert _filters(session, country="DE", skill="distributed")["total_matches"] == 0


def test_filters_paginate_and_report_total(session):
    for i in range(12):
        ingest_profile(
            session,
            make_profile(
                external_id=f"p{i}", url=f"https://github.com/p{i}",
                raw={"login": f"p{i}"}, name=f"Person {i}", usernames=[f"github:p{i}"],
                country="US",
            ),
        )
    page = _filters(session, country="US", limit=5)
    assert page["count"] == 5 and page["total_matches"] == 12
    assert page["has_more"] and page["next_offset"] == 5
    last = _filters(session, country="US", limit=5, offset=10)
    assert last["count"] == 2 and not last["has_more"]


def test_sort_is_factual_not_ranked(session):
    ingest_profile(session, make_profile(name="Zoe Last", country="US"))
    ingest_profile(
        session,
        make_profile(external_id="a", url="https://github.com/a", raw={"login": "a"},
                     name="Aaron First", usernames=["github:a"], country="US"),
    )
    names = [r["canonical_name"] for r in _filters(session, sort="name")["results"]]
    assert names == sorted(names)
    # no score/rank fields anywhere in the payload
    assert "score" not in str(_filters(session, country="US"))


def test_facets_list_available_values(session):
    from rip.api import facets

    ingest_profile(session, make_profile(name="Asha Rao", country="IN"))
    countries = facets(field="country", limit=10, db=session)
    assert countries["values"] == [{"value": "IN", "people": 1}]
    sources = facets(field="source", limit=10, db=session)
    assert {v["value"] for v in sources["values"]} == {"github"}

    from fastapi import HTTPException
    try:
        facets(field="nonsense", limit=10, db=session)
        raise AssertionError("should reject unknown facet")
    except HTTPException as exc:
        assert exc.status_code == 422


def test_place_name_is_never_treated_as_a_person_name(session):
    """Regression: "python developers in Hyderabad" searched for people NAMED
    Hyderabad, guaranteeing zero results instead of reporting the gap."""
    seed(session)
    parsed = parse(session, "top python developers in Hyderabad")
    assert parsed.name_terms == []            # not a name filter
    assert "Hyderabad" in parsed.unmatched_terms  # reported honestly


def test_capitalised_word_is_a_name_filter_only_when_someone_has_it(session):
    seed(session)
    assert parse(session, "find Grace").name_terms == ["Grace"]
    assert parse(session, "find Zzznobody").name_terms == []


def test_country_names_become_country_filters(session):
    from rip.normalize import OrgAffiliation

    ingest_profile(session, make_profile(name="Asha Rao", country="IN",
                                         organizations=[OrgAffiliation(name="Acme Labs")]))
    parsed = parse(session, "researchers in India")
    assert parsed.countries == ["IN"]
    assert [p.canonical_name for p in execute(session, parsed)] == ["Asha Rao"]
    assert parse(session, "people in Germany").countries == ["DE"]


def test_preposition_phrases_do_not_hijack_skills(session):
    """"in India" must not match a skill merely containing that phrase."""
    from rip.normalize import EvidenceItem

    ingest_profile(
        session,
        make_profile(name="Ravi Kumar", country="IN",
                     evidence=[EvidenceItem(attribute_type="research_interest",
                                            value="Social and Economic Development in India")]),
    )
    parsed = parse(session, "machine learning researchers in India")
    assert parsed.countries == ["IN"]
    assert "Social and Economic Development in India" not in parsed.skills


class _FullPayloadSearcher:
    """A provider that returns whole person records, like Exa does."""

    def __init__(self, calls):
        self._calls = calls

    def normalize(self, raw):
        from rip.connectors.exa import ExaConnector

        return ExaConnector.normalize(ExaConnector.__new__(ExaConnector), raw)

    def search_people(self, query, limit=10):
        self._calls.append(query)
        return [{
            "id": "px1", "name": "Nadia Rahman", "affiliation": "Zeta Corp",
            "role": "Growth Lead", "location": "Lisbon, Portugal",
            "raw": {
                "id": "https://exa.ai/library/person/px1",
                "url": "https://linkedin.com/in/nadia",
                "title": "Nadia Rahman",
                "text": "# Nadia Rahman\n\nGrowth Lead at Zeta Corp\n\nLisbon, Portugal (PT)\n",
                "entities": [{
                    "id": "https://exa.ai/library/person/px1", "type": "person",
                    "properties": {"name": "Nadia Rahman", "location": "Lisbon, Portugal",
                                   "workHistory": [{"title": "Growth Lead",
                                                    "company": {"name": "Zeta Corp"}}],
                                   "educationHistory": []},
                }],
            },
        }]


def test_paid_results_are_stored_so_the_next_query_is_free(session, monkeypatch):
    """A provider that returns full records should never be paid for twice."""
    from rip.api import nl_query
    from rip.models import Person, SearchCache

    calls = []
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr("rip.connectors.get_connector", lambda s: _FullPayloadSearcher(calls))
    monkeypatch.setattr("rip.nlq.SUGGESTION_SEARCHERS",
                        (("exa", __import__("rip.nlq", fromlist=["x"])._search_exa, True),))

    first = nl_query(q="growth leads at Zeta Corp", discover="true", db=session)
    assert first["stored_from_live"] == 1
    assert len(calls) == 1
    assert session.query(Person).filter_by(canonical_name="Nadia Rahman").count() == 1
    # the freshly stored person is returned as a result, not just a suggestion
    assert any(r["canonical_name"] == "Nadia Rahman" for r in first["results"])

    second = nl_query(q="growth leads at Zeta Corp", discover="true", db=session)
    assert len(calls) == 1          # provider not queried again
    assert second["stored_from_live"] == 0
    cache = session.query(SearchCache).filter_by(provider="exa").one()
    assert cache.result_count == 1 and cache.stored_count == 1


def test_cache_expires_after_the_ttl(session, monkeypatch):
    from datetime import datetime, timedelta, timezone

    import rip.nlq as nlq
    from rip.models import SearchCache

    nlq._cache_record(session, "exa", "some query", 3, 3)
    assert nlq._cache_lookup(session, "exa", "some query") is not None
    row = session.query(SearchCache).one()
    row.ran_at = datetime.now(timezone.utc) - timedelta(days=nlq.SEARCH_TTL_DAYS + 1)
    session.commit()
    assert nlq._cache_lookup(session, "exa", "some query") is None


def test_query_normalisation_ignores_word_order(session):
    import rip.nlq as nlq

    assert nlq._norm_query("growth leads at Zeta") == nlq._norm_query("Zeta growth at leads")


def test_empty_result_names_the_filter_responsible(session):
    from rip.nlq import diagnose_empty
    from rip.normalize import EvidenceItem, OrgAffiliation

    ingest_profile(
        session,
        make_profile(name="Ann Fields", organizations=[OrgAffiliation(name="Zomato")]),
    )
    ingest_profile(
        session,
        make_profile(external_id="b", url="https://github.com/b", raw={"login": "b"},
                     name="Bo Chen", usernames=["github:b"],
                     evidence=[EvidenceItem(attribute_type="skill", value="Economic Growth")]),
    )
    parsed = parse(session, "growth people at Zomato")
    assert execute(session, parsed) == []
    why = diagnose_empty(session, parsed)
    assert why and why["would_match"] >= 1
    assert "Dropping" in why["message"]


def test_no_diagnosis_when_only_one_filter(session):
    from rip.nlq import diagnose_empty

    seed(session)
    parsed = parse(session, "Zzznothing")
    assert diagnose_empty(session, parsed) is None
