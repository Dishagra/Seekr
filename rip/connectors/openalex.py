"""OpenAlex connector — open scholarly graph API (no key required).

Identifier: OpenAlex author ID (e.g. "A5023888391") or full OpenAlex URL.
Set OPENALEX_MAILTO to join their polite pool (faster, more reliable).
Extracts: name/aliases, ORCID (strong identity key), institutional affiliations,
research topics as evidence, top-cited works as publications.

Use `search_authors(name)` first to find candidate author IDs.
"""

import os

from ..normalize import (
    EvidenceItem,
    NormalizedProfile,
    OrgAffiliation,
    PublicationData,
)
from .base import BaseConnector

API = "https://api.openalex.org"
MAX_WORKS = 25


class OpenAlexConnector(BaseConnector):
    source = "openalex"
    source_type = "scholarly"
    min_request_interval = 0.15  # OpenAlex allows 10 req/s

    def _params(self, extra: dict | None = None) -> dict:
        params = dict(extra or {})
        mailto = os.environ.get("OPENALEX_MAILTO")
        if mailto:
            params["mailto"] = mailto
        return params

    def search_authors(self, name: str, limit: int = 10) -> list[dict]:
        """Candidate authors for a name — caller picks the right ID to ingest."""
        data = self.get_json(
            f"{API}/authors", params=self._params({"search": name, "per-page": limit})
        )
        return [
            {
                "id": a["id"].rsplit("/", 1)[-1],
                "name": a.get("display_name"),
                "orcid": a.get("orcid"),
                "works_count": a.get("works_count"),
                "cited_by": a.get("cited_by_count"),
                "affiliation": (a.get("last_known_institutions") or [{}])[0].get("display_name")
                if a.get("last_known_institutions")
                else None,
            }
            for a in data.get("results", [])
        ]

    def search_authors_by_topic(self, topic: str, limit: int = 10) -> list[dict]:
        """Authors who published on a topic.

        Author-name search is the wrong instrument for "computer vision
        researchers" — it returns people surnamed Rust and index entities like
        "Computer Vision Foundation". Searching works and taking their authors
        finds people who actually work on the subject.
        """
        data = self.get_json(
            f"{API}/works",
            params=self._params({"search": topic, "per-page": min(50, limit * 5)}),
        )
        seen: dict[str, dict] = {}
        for work in data.get("results", []):
            for authorship in work.get("authorships", []):
                author = authorship.get("author") or {}
                aid = (author.get("id") or "").rsplit("/", 1)[-1]
                name = author.get("display_name")
                if not aid or not name or aid in seen:
                    continue
                insts = authorship.get("institutions") or [{}]
                seen[aid] = {
                    "id": aid,
                    "name": name,
                    "orcid": author.get("orcid"),
                    "works_count": None,
                    "cited_by": None,
                    "affiliation": insts[0].get("display_name"),
                }
                if len(seen) >= limit:
                    return list(seen.values())
        return list(seen.values())

    def fetch(self, identifier: str) -> NormalizedProfile:
        author_id = identifier.rsplit("/", 1)[-1]
        author = self.get_json(f"{API}/authors/{author_id}", params=self._params())
        works = self.get_json(
            f"{API}/works",
            params=self._params(
                {
                    "filter": f"author.id:{author_id}",
                    "sort": "cited_by_count:desc",
                    "per-page": MAX_WORKS,
                }
            ),
        )
        return self.normalize(author, works.get("results", []))

    def renormalize(self, external_id: str, raw: dict) -> NormalizedProfile:
        return self.normalize(raw["author"], raw["works"])

    def normalize(self, author: dict, works: list[dict]) -> NormalizedProfile:
        author_id = author["id"].rsplit("/", 1)[-1]
        name = author.get("display_name")

        country = next(
            (
                inst.get("country_code")
                for inst in (author.get("last_known_institutions") or [])
                if inst.get("country_code")
            ),
            None,
        )
        organizations = [
            OrgAffiliation(
                name=inst["display_name"],
                relation="worked_at",
                org_type=inst.get("type"),
                is_current=True,
                url=None,
            )
            for inst in (author.get("last_known_institutions") or [])
            if inst.get("display_name")
        ]

        evidence = [
            EvidenceItem(
                attribute_type="research_interest",
                value=topic["display_name"],
                extracted_info=f"OpenAlex topic (count={topic.get('count')})",
                url=author.get("id"),
                confidence=0.6,
            )
            for topic in (author.get("topics") or [])[:15]
            if topic.get("display_name")
        ]

        publications = []
        for work in works:
            title = work.get("display_name") or work.get("title")
            if not title:
                continue
            authorships = work.get("authorships") or []
            authors = [
                (a.get("author") or {}).get("display_name")
                for a in authorships
            ]
            position = None
            for i, a in enumerate(authorships):
                if ((a.get("author") or {}).get("id") or "").endswith(author_id):
                    position = i + 1
                    break
            venue = None
            loc = work.get("primary_location") or {}
            if loc.get("source"):
                venue = loc["source"].get("display_name")
            publications.append(
                PublicationData(
                    title=title[:1024],
                    external_id=work["id"].rsplit("/", 1)[-1],
                    venue=venue,
                    published_date=work.get("publication_date"),
                    url=work.get("doi") or work.get("id"),
                    doi=(work.get("doi") or "").replace("https://doi.org/", "") or None,
                    citations=work.get("cited_by_count"),
                    topics=[
                        t["display_name"] for t in (work.get("topics") or [])[:5]
                        if t.get("display_name")
                    ],
                    raw_authors=[a for a in authors if a],
                    author_position=position,
                )
            )

        return NormalizedProfile(
            source=self.source,
            source_type=self.source_type,
            external_id=author_id,
            url=author.get("id") or f"{API}/authors/{author_id}",
            raw={"author": author, "works": works},
            name=name,
            aliases=list(author.get("display_name_alternatives") or []),
            country=country.upper() if country else None,
            orcid=author.get("orcid"),
            organizations=organizations,
            evidence=evidence,
            publications=publications,
        )
