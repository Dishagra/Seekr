"""ORCID connector — public read API (pub.orcid.org, no key required).

Identifier: ORCID iD, e.g. "0000-0002-1825-0097" (a full https://orcid.org/...
URL also works).
Extracts: name + other-names, keywords as research interests, researcher URLs
(strong resolution links), public emails, employment/education affiliations
with roles and dates, works as publications (DOI when present).

ORCID data is largely self-asserted by the researcher; evidence confidence is
set accordingly, and claims added by external sources (e.g. Crossref) surface
via normal cross-source corroboration.
"""

from ..normalize import (
    EvidenceItem,
    NormalizedProfile,
    OrgAffiliation,
    PublicationData,
)
from .base import BaseConnector

API = "https://pub.orcid.org/v3.0"


def _date(d: dict | None) -> str | None:
    """ORCID fuzzy date {'year': {'value': '2012'}, 'month': ..., 'day': ...} -> ISO-ish string."""
    if not d:
        return None
    parts = []
    for key in ("year", "month", "day"):
        v = (d.get(key) or {}).get("value") if d.get(key) else None
        if not v:
            break
        parts.append(v)
    return "-".join(parts) or None


class OrcidConnector(BaseConnector):
    source = "orcid"
    source_type = "researcher_registry"
    min_request_interval = 0.5  # public API limit: ~12 req/s burst, stay well under

    def default_headers(self) -> dict:
        headers = super().default_headers()
        headers["Accept"] = "application/json"
        return headers

    def fetch(self, identifier: str) -> NormalizedProfile:
        orcid_id = identifier.rstrip("/").rsplit("/", 1)[-1].upper()
        record = self.get_json(f"{API}/{orcid_id}/record")
        return self.normalize(record)

    def renormalize(self, external_id: str, raw: dict) -> NormalizedProfile:
        return self.normalize(raw)

    def normalize(self, record: dict) -> NormalizedProfile:
        orcid_id = record["orcid-identifier"]["path"]
        person = record.get("person") or {}

        name_block = person.get("name") or {}
        given = ((name_block.get("given-names") or {}).get("value") or "").strip()
        family = ((name_block.get("family-name") or {}).get("value") or "").strip()
        credit = (name_block.get("credit-name") or {}).get("value")
        name = credit or " ".join(x for x in (given, family) if x) or None

        aliases = [
            o["content"]
            for o in ((person.get("other-names") or {}).get("other-name") or [])
            if o.get("content")
        ]

        evidence = [
            EvidenceItem(
                attribute_type="research_interest",
                value=k["content"],
                extracted_info="self-reported ORCID keyword",
                url=f"https://orcid.org/{orcid_id}",
                confidence=0.5,
            )
            for k in ((person.get("keywords") or {}).get("keyword") or [])
            if k.get("content")
        ]

        websites = [
            u["url"]["value"]
            for u in ((person.get("researcher-urls") or {}).get("researcher-url") or [])
            if (u.get("url") or {}).get("value")
        ]

        emails = [
            e["email"]
            for e in ((person.get("emails") or {}).get("email") or [])
            if e.get("email")
        ]

        activities = record.get("activities-summary") or {}
        organizations: list[OrgAffiliation] = []
        for relation, section, summary_key, org_type in (
            ("worked_at", "employments", "employment-summary", None),
            ("studied_at", "educations", "education-summary", "university"),
        ):
            groups = (activities.get(section) or {}).get("affiliation-group") or []
            for group in groups:
                for summary_wrap in group.get("summaries") or []:
                    summary = summary_wrap.get(summary_key) or {}
                    org = summary.get("organization") or {}
                    if not org.get("name"):
                        continue
                    end = _date(summary.get("end-date"))
                    organizations.append(
                        OrgAffiliation(
                            name=org["name"],
                            relation=relation,
                            role=summary.get("role-title"),
                            org_type=org_type,
                            start_date=_date(summary.get("start-date")),
                            end_date=end,
                            is_current=relation == "worked_at" and end is None,
                            url=f"https://orcid.org/{orcid_id}",
                        )
                    )

        publications: list[PublicationData] = []
        for group in (activities.get("works") or {}).get("group") or []:
            summaries = group.get("work-summary") or []
            if not summaries:
                continue
            work = summaries[0]  # first summary is the preferred version
            title = ((work.get("title") or {}).get("title") or {}).get("value")
            if not title:
                continue
            doi = None
            for ext in ((work.get("external-ids") or {}).get("external-id") or []):
                if ext.get("external-id-type") == "doi" and ext.get("external-id-relationship") == "self":
                    doi = ((ext.get("external-id-normalized") or {}).get("value")
                           or ext.get("external-id-value"))
                    break
            url = (work.get("url") or {}).get("value")
            publications.append(
                PublicationData(
                    title=title[:1024],
                    external_id=f"doi:{doi}" if doi else f"orcid-work:{work.get('put-code')}",
                    venue=(work.get("journal-title") or {}).get("value"),
                    published_date=_date(work.get("publication-date")),
                    url=url or (f"https://doi.org/{doi}" if doi else None),
                    doi=doi,
                )
            )

        return NormalizedProfile(
            source=self.source,
            source_type=self.source_type,
            external_id=orcid_id,
            url=f"https://orcid.org/{orcid_id}",
            raw=record,
            name=name,
            aliases=aliases,
            orcid=orcid_id,
            emails=emails,
            websites=websites,
            organizations=organizations,
            evidence=evidence,
            publications=publications,
        )
