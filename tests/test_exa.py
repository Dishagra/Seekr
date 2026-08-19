"""Exa people connector (fixture data, no network)."""

from rip.connectors.exa import ExaConnector
from rip.ingest import ingest_profile
from rip.models import Evidence, Person

RESULT = {
    "id": "https://exa.ai/library/person/ybx9zz9d72n",
    "url": "https://linkedin.com/in/pooja-bordoloi",
    "title": "Pooja Bordoloi",
    "text": (
        "# Pooja Bordoloi\n\nProgram Manager at OYO\n\n"
        "Gurugram, Haryana, India (IN)\n\n"
        "## Experience\n\n### Program Manager - [OYO](x) (Current)\n\n"
        "## Skills\n\nprogram manager • program management • management\n"
    ),
    "entities": [{
        "id": "https://exa.ai/library/person/ybx9zz9d72n",
        "type": "person",
        "properties": {
            "name": "Pooja Bordoloi",
            "location": "Gurugram, Haryana, India",
            "workHistory": [
                {"title": "Program Manager", "company": {"name": "OYO"}},
                {"title": "Analyst", "company": {"name": "Earlier Co"}},
            ],
            "educationHistory": [{"school": {"name": "Delhi University"}}],
        },
    }],
}


def profile():
    return ExaConnector.normalize(ExaConnector.__new__(ExaConnector), RESULT)


def test_normalizes_person_entity():
    p = profile()
    assert p.name == "Pooja Bordoloi"
    assert p.external_id == "ybx9zz9d72n"
    assert p.country == "IN"
    assert p.location == "Gurugram, Haryana, India"
    orgs = [(o.name, o.relation, o.is_current) for o in p.organizations]
    assert ("OYO", "worked_at", True) in orgs
    assert ("Earlier Co", "worked_at", False) in orgs      # only the first is current
    assert ("Delhi University", "studied_at", False) in orgs
    skills = {e.value for e in p.evidence if e.attribute_type == "skill"}
    assert skills == {"program manager", "program management", "management"}


def test_originating_url_is_preserved_for_provenance():
    """The LinkedIn origin must stay visible, never silently dropped."""
    p = profile()
    assert "https://linkedin.com/in/pooja-bordoloi" in p.linked_urls
    role = next(e for e in p.evidence if e.attribute_type == "role")
    assert "linkedin.com" in role.url


def test_ingests_with_role_and_country(session):
    person = ingest_profile(session, profile())
    assert person.current_organization == "OYO"
    assert person.current_role == "Program Manager"
    assert person.country == "IN"
    assert session.query(Person).count() == 1
    assert session.query(Evidence).filter_by(attribute_type="role").count() == 1


def test_search_requires_a_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    connector = ExaConnector.__new__(ExaConnector)
    try:
        connector.search_people("anything")
        raise AssertionError("should refuse without a key")
    except RuntimeError as exc:
        assert "EXA_API_KEY" in str(exc)


def test_non_person_results_are_ignored(monkeypatch):
    connector = ExaConnector.__new__(ExaConnector)
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(
        ExaConnector, "_post",
        lambda self, path, payload: {"results": [
            {"id": "x", "url": "u", "entities": [{"type": "organization"}]},
            RESULT,
        ]},
    )
    people = connector.search_people("q")
    assert [p["name"] for p in people] == ["Pooja Bordoloi"]
    assert people[0]["affiliation"] == "OYO"
