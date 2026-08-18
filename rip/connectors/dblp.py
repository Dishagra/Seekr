"""dblp connector — computer science bibliography (open API, no key).

Identifier: dblp PID, e.g. "10/3248" (find one with `search_authors`).
dblp asks for courteous crawling; we keep a 2s minimum interval.

Person records are unusually rich for resolution: they list homepage,
Google Scholar, Wikipedia, Wikidata and personal-site URLs (all become
strong identity keys), plus affiliations and awards. Publications carry
co-author PIDs, which feed bulk discovery.
"""

import xml.etree.ElementTree as ET

from ..normalize import (
    EvidenceItem,
    NormalizedProfile,
    OrgAffiliation,
    PublicationData,
)
from .base import BaseConnector

BASE = "https://dblp.org"
MAX_PUBS = 100
PUB_TAGS = {"article", "inproceedings", "proceedings", "book", "incollection", "phdthesis"}


class DblpConnector(BaseConnector):
    source = "dblp"
    source_type = "scholarly"
    min_request_interval = 2.0

    def search_authors(self, name: str, limit: int = 10) -> list[dict]:
        data = self.get_json(
            f"{BASE}/search/author/api", params={"q": name, "format": "json", "h": limit}
        )
        hits = ((data.get("result") or {}).get("hits") or {}).get("hit") or []
        if isinstance(hits, dict):
            hits = [hits]
        out = []
        for hit in hits:
            info = hit.get("info") or {}
            url = info.get("url") or ""
            out.append(
                {
                    "pid": url.split("/pid/", 1)[-1] if "/pid/" in url else None,
                    "name": info.get("author"),
                    "url": url,
                }
            )
        return out

    def fetch(self, identifier: str) -> NormalizedProfile:
        pid = identifier.strip().strip("/")
        if "/pid/" in pid:
            pid = pid.split("/pid/", 1)[-1]
        xml_text = self.get_text(f"{BASE}/pid/{pid}.xml")
        return self.normalize(pid, xml_text)

    def renormalize(self, external_id: str, raw: dict) -> NormalizedProfile:
        if "xml" not in raw:
            raise NotImplementedError(
                "dblp record stored before full-XML retention; re-fetch instead"
            )
        return self.normalize(external_id, raw["xml"])

    def normalize(self, pid: str, xml_text: str) -> NormalizedProfile:
        root = ET.fromstring(xml_text)
        name = root.get("name")
        person_el = root.find("person")

        websites: list[str] = []
        organizations: list[OrgAffiliation] = []
        evidence: list[EvidenceItem] = []
        aliases: list[str] = []
        profile_url = f"{BASE}/pid/{pid}"

        if person_el is not None:
            for url_el in person_el.findall("url"):
                if url_el.text:
                    websites.append(url_el.text.strip())
            for author_el in person_el.findall("author"):
                if author_el.text and author_el.text != name:
                    aliases.append(author_el.text)
            for note in person_el.findall("note"):
                note_type = note.get("type")
                if note_type == "affiliation" and note.text:
                    # e.g. "University of Toronto, Department of Computer Science, ON, Canada"
                    org_name = note.text.split(",")[0].strip()
                    organizations.append(
                        OrgAffiliation(name=org_name, relation="worked_at", url=profile_url)
                    )
                    evidence.append(
                        EvidenceItem(
                            attribute_type="affiliation",
                            value=note.text.strip()[:512],
                            url=profile_url,
                            confidence=0.7,
                        )
                    )
                elif note_type == "award" and note.text:
                    label = note.get("label")
                    evidence.append(
                        EvidenceItem(
                            attribute_type="award",
                            value=f"{note.text.strip()} ({label})" if label else note.text.strip(),
                            url=profile_url,
                            confidence=0.85,
                        )
                    )

        publications: list[PublicationData] = []
        coauthor_pids: list[dict] = []  # kept in raw for discovery
        records = root.findall("r")
        for r in records:
            pub_el = next((child for child in r if child.tag in PUB_TAGS), None)
            if pub_el is None:
                continue
            title = (pub_el.findtext("title") or "").strip().rstrip(".")
            if not title:
                continue
            authors = []
            position = None
            for i, author_el in enumerate(pub_el.findall("author")):
                authors.append(author_el.text or "")
                author_pid = author_el.get("pid")
                if author_pid == pid:
                    position = i + 1
                elif author_pid:
                    coauthor_pids.append({"pid": author_pid, "name": author_el.text})
            venue = pub_el.findtext("journal") or pub_el.findtext("booktitle")
            url = pub_el.findtext("ee") or f"{BASE}/rec/{pub_el.get('key')}"
            doi = None
            ee = pub_el.findtext("ee") or ""
            if "doi.org/" in ee:
                doi = ee.split("doi.org/", 1)[-1]
            if len(publications) < MAX_PUBS:
                publications.append(
                    PublicationData(
                        title=title[:1024],
                        external_id=f"doi:{doi}" if doi else f"dblp:{pub_el.get('key')}",
                        venue=venue,
                        published_date=pub_el.findtext("year"),
                        url=url,
                        doi=doi,
                        raw_authors=[a for a in authors if a],
                        author_position=position,
                    )
                )

        seen = set()
        coauthors_dedup = []
        for c in coauthor_pids:
            if c["pid"] not in seen:
                seen.add(c["pid"])
                coauthors_dedup.append(c)

        return NormalizedProfile(
            source=self.source,
            source_type=self.source_type,
            external_id=pid,
            url=profile_url,
            raw={
                "name": name,
                "publication_count": len(records),
                "websites": websites,
                "coauthors": coauthors_dedup,
                # full XML so the corpus can be re-parsed without re-crawling
                "xml": xml_text,
            },
            name=name,
            aliases=aliases,
            websites=websites,
            organizations=organizations,
            evidence=evidence,
            publications=publications,
        )
