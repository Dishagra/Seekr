"""Phase 6: person neighborhood graph."""

import pytest

from rip.api import get_graph
from rip.ingest import ingest_profile
from rip.normalize import OrgAffiliation, PublicationData
from tests.test_resolution import make_profile


def _person(session, name, external_id, pubs=(), org=None):
    return ingest_profile(
        session,
        make_profile(
            source="openalex",
            external_id=external_id,
            url=f"https://openalex.org/{external_id}",
            raw={"id": external_id},
            name=name,
            usernames=[],
            organizations=[OrgAffiliation(name=org, is_current=True)] if org else [],
            publications=[
                PublicationData(title=t, external_id=f"doi:{t}", doi=t) for t in pubs
            ],
        ),
    )


def test_graph_has_org_and_coauthor_edges(session):
    a = _person(session, "Ada One", "A1", pubs=["paper-x", "paper-y"], org="Acme Labs")
    b = _person(session, "Bob Two", "A2", pubs=["paper-x"], org="Globex")
    c = _person(session, "Cy Three", "A3", pubs=["paper-y"])

    graph = get_graph(a.id, depth=1, limit_coauthors=20, db=session)
    node_ids = {n["id"] for n in graph["nodes"]}
    assert a.id in node_ids and b.id in node_ids and c.id in node_ids
    assert any(n["type"] == "organization" and n["label"] == "Acme Labs" for n in graph["nodes"])

    coauthor_edges = [e for e in graph["edges"] if e["type"] == "coauthor"]
    assert {e["to"] for e in coauthor_edges} == {b.id, c.id}
    assert all(e["shared_publications"] == 1 for e in coauthor_edges)
    assert all(e["via_publication_id"] for e in coauthor_edges)

    org_edges = [e for e in graph["edges"] if e["type"] == "worked_at"]
    assert len(org_edges) == 1 and org_edges[0]["is_current"] is True


def test_shared_publication_count_is_an_edge_weight(session):
    a = _person(session, "Ada One", "A1", pubs=["p1", "p2", "p3"])
    b = _person(session, "Bob Two", "A2", pubs=["p1", "p2", "p3"])
    _person(session, "Cy Three", "A3", pubs=["p1"])
    graph = get_graph(a.id, depth=1, limit_coauthors=20, db=session)
    weights = {e["to"]: e["shared_publications"] for e in graph["edges"] if e["type"] == "coauthor"}
    assert weights[b.id] == 3
    # no ranking fields leak into the payload
    assert "score" not in str(graph) and "rank" not in str(graph)


def test_coauthor_limit_bounds_payload(session):
    a = _person(session, "Ada One", "A1", pubs=["shared"])
    for i in range(2, 12):
        _person(session, f"Co {i}", f"A{i}", pubs=["shared"])
    graph = get_graph(a.id, depth=1, limit_coauthors=5, db=session)
    assert len([e for e in graph["edges"] if e["type"] == "coauthor"]) == 5


def test_isolated_person_has_only_self(session):
    a = _person(session, "Solo Person", "A9")
    graph = get_graph(a.id, depth=1, limit_coauthors=20, db=session)
    assert graph["nodes"] == [{"id": a.id, "type": "person", "label": "Solo Person"}]
    assert graph["edges"] == []


def test_unknown_person_404s(session):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        get_graph("no-such-uuid", depth=1, limit_coauthors=20, db=session)
    assert exc.value.status_code == 404


def test_merged_person_excluded_from_coauthors(session):
    from rip.review import merge_persons

    a = _person(session, "Ada One", "A1", pubs=["p1"])
    b = _person(session, "Bob Two", "A2", pubs=["p1"])
    c = _person(session, "Bob Twoo", "A3", pubs=["p1"])
    merge_persons(session, b.id, c.id)
    graph = get_graph(a.id, depth=1, limit_coauthors=20, db=session)
    coauthor_ids = {e["to"] for e in graph["edges"] if e["type"] == "coauthor"}
    assert c.id not in coauthor_ids  # tombstone hidden
    assert b.id in coauthor_ids
