"""Phase 2B: single-page web connector (fixture HTML, no network)."""

from rip.connectors.web import WebConnector
from rip.ingest import ingest_profile
from rip.models import Evidence, Person

HTML = """<!doctype html>
<html><head>
<title>Dr. Jane Doe — Systems Research</title>
<meta property="og:description" content="Research engineer working on distributed storage.">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Person","name":"Jane Doe",
 "jobTitle":"Principal Engineer","affiliation":{"@type":"Organization","name":"Acme Labs"},
 "knowsAbout":["Distributed Systems","Consensus Protocols"]}
</script>
</head><body>
<p>Contact: jane@example.edu</p>
<p>ORCID: 0000-0002-1111-2222</p>
<a href="https://github.com/jdoe">code</a>
<a href="https://www.dblp.org/pid/99/1234.html">papers</a>
<a href="/local/page">internal</a>
<a href="https://example.com/unrelated">unrelated</a>
</body></html>"""


def parse(url="https://janedoe.ai/about", html=HTML):
    return WebConnector.normalize(WebConnector.__new__(WebConnector), url, html)


def test_extracts_jsonld_person():
    p = parse()
    assert p.name == "Jane Doe"
    assert p.organizations[0].name == "Acme Labs"
    assert p.organizations[0].role == "Principal Engineer"
    skills = {e.value for e in p.evidence if e.attribute_type == "skill"}
    assert skills == {"Distributed Systems", "Consensus Protocols"}


def test_extracts_identity_signals():
    p = parse()
    assert p.orcid == "0000-0002-1111-2222"
    assert "jane@example.edu" in p.emails
    assert "https://github.com/jdoe" in p.linked_urls
    assert any("dblp.org/pid/99/1234" in u for u in p.linked_urls)
    # non-profile hosts are not collected as identity links
    assert not any("example.com/unrelated" in u for u in p.linked_urls)


def test_external_id_is_normalized_url():
    assert parse("https://WWW.JaneDoe.ai/about/").external_id == "janedoe.ai/about"


def test_falls_back_to_title_when_no_jsonld():
    p = parse(html="<html><head><title>Ada Lovelace</title></head><body>hi</body></html>")
    assert p.name == "Ada Lovelace"
    assert p.organizations == []


def test_renormalize_from_stored_raw(session):
    person = ingest_profile(session, parse())
    record = person.identities[0].source_record
    again = WebConnector.renormalize(WebConnector.__new__(WebConnector), record.external_id, record.raw)
    assert again.name == "Jane Doe"
    assert again.orcid == "0000-0002-1111-2222"


def test_ingest_produces_evidence_and_person(session):
    person = ingest_profile(session, parse())
    assert person.canonical_name == "Jane Doe"
    assert session.query(Person).count() == 1
    bios = session.query(Evidence).filter_by(attribute_type="bio").all()
    assert bios and "distributed storage" in bios[0].value


def test_web_merges_into_person_via_orcid(session):
    from tests.test_enrich import orcid_profile

    p1 = ingest_profile(session, orcid_profile())
    p2 = ingest_profile(session, parse())
    assert p1.id == p2.id  # ORCID on the page is a strong key


def test_robots_disallow_blocks_fetch(monkeypatch):
    connector = WebConnector.__new__(WebConnector)

    class FakeResp:
        status_code = 200
        text = "User-agent: *\nDisallow: /private"

    class FakeClient:
        def get(self, url, timeout=None):
            return FakeResp()

    connector._client = FakeClient()
    assert connector._robots_allows("https://site.example/public") is True
    assert connector._robots_allows("https://site.example/private/page") is False


CV_HTML = """<html><head><title>Prof A Sharma</title></head><body>
<a href="/files/cv.pdf">Curriculum Vitae</a>
<a href="https://example.edu/~a/resume.pdf">My resume (PDF)</a>
<a href="/papers/cvpr2021.pdf">CVPR 2021 paper</a>
<a href="/papers/discovery.pdf">Discovery of things</a>
<a href="/teaching">Teaching</a>
</body></html>"""


def test_cv_links_only_when_page_says_so():
    p = parse("https://example.edu/~a/", CV_HTML)
    cvs = {e.value for e in p.evidence if e.attribute_type == "cv_url"}
    assert cvs == {
        "https://example.edu/files/cv.pdf",
        "https://example.edu/~a/resume.pdf",
    }
    # "CVPR" is not a CV, and an unrelated PDF is not a CV
    assert not any("cvpr" in c for c in cvs)
    assert not any("discovery" in c for c in cvs)


def test_cv_evidence_keeps_provenance():
    p = parse("https://example.edu/~a/", CV_HTML)
    cv = next(e for e in p.evidence if e.attribute_type == "cv_url")
    assert cv.url == "https://example.edu/~a/"      # the page it was found on
    assert "linked as" in cv.extracted_info          # and how it was identified


def test_documents_endpoint_lists_only_found_links(session):
    from rip.api import get_documents

    person = ingest_profile(session, parse("https://example.edu/~a/", CV_HTML))
    docs = get_documents(person.id, db=session)
    assert {c["url"] for c in docs["cvs"]} == {
        "https://example.edu/files/cv.pdf",
        "https://example.edu/~a/resume.pdf",
    }
    assert all(c["found_on"] == "https://example.edu/~a/" for c in docs["cvs"])
    assert "generated by seekr" in docs["note"].lower()  # we do not create documents


def test_person_without_cv_reports_none(session):
    from rip.api import get_documents
    from tests.test_enrich import orcid_profile

    person = ingest_profile(session, orcid_profile())
    assert get_documents(person.id, db=session)["cvs"] == []
