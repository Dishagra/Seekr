"""Bulk discovery: mine existing source records for new people.

Two kinds of extractors:
- raw-only: read stored raw payloads, zero extra API calls
  (OpenAlex co-authors)
- live: bounded follow-up API calls
  (GitHub contributors of a person's top repos)

Discovered people become DiscoveryLead rows (a queue), drained separately by
`ingest-leads` so discovery volume never outruns rate limits.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .connectors import get_connector
from .ingest import run_connector
from .models import DiscoveryLead, SourceRecord


def _add_lead(
    session: Session, source: str, identifier: str, via_record: SourceRecord, reason: str
) -> bool:
    """Insert if new and not already ingested. Returns True if a lead was added."""
    exists = session.execute(
        select(DiscoveryLead.id).where(
            DiscoveryLead.source == source, DiscoveryLead.identifier == identifier
        )
    ).first()
    if exists:
        return False
    already_ingested = session.execute(
        select(SourceRecord.id).where(
            SourceRecord.source == source, SourceRecord.external_id == identifier
        )
    ).first()
    if already_ingested:
        return False
    session.add(
        DiscoveryLead(
            source=source,
            identifier=identifier,
            discovered_via_record_id=via_record.id,
            reason=reason[:1000],
        )
    )
    return True


def discover_openalex_coauthors(session: Session) -> int:
    """Raw-only: co-authors on stored OpenAlex works."""
    added = 0
    records = (
        session.execute(select(SourceRecord).where(SourceRecord.source == "openalex"))
        .scalars()
        .all()
    )
    for record in records:
        own_name = (record.raw.get("author") or {}).get("display_name")
        for work in record.raw.get("works") or []:
            title = work.get("display_name") or "untitled"
            for authorship in work.get("authorships") or []:
                author = authorship.get("author") or {}
                author_id = (author.get("id") or "").rsplit("/", 1)[-1]
                if not author_id or author_id == record.external_id:
                    continue
                reason = f"co-author of {own_name or record.external_id} on '{title[:120]}'"
                if _add_lead(session, "openalex", author_id, record, reason):
                    added += 1
    session.commit()
    return added


def discover_dblp_coauthors(session: Session) -> int:
    """Raw-only: co-author PIDs stored in dblp source records."""
    added = 0
    records = (
        session.execute(select(SourceRecord).where(SourceRecord.source == "dblp"))
        .scalars()
        .all()
    )
    for record in records:
        own_name = record.raw.get("name") or record.external_id
        for coauthor in record.raw.get("coauthors") or []:
            pid = coauthor.get("pid")
            if not pid:
                continue
            reason = f"dblp co-author of {own_name} ({coauthor.get('name')})"
            if _add_lead(session, "dblp", pid, record, reason):
                added += 1
    session.commit()
    return added


def discover_github_contributors(
    session: Session, max_repos_per_person: int = 3, max_contributors_per_repo: int = 10
) -> int:
    """Live: contributors of each known person's top-starred repos. Bounded."""
    connector = get_connector("github")
    added = 0
    records = (
        session.execute(select(SourceRecord).where(SourceRecord.source == "github"))
        .scalars()
        .all()
    )
    for record in records:
        repos = [r for r in (record.raw.get("repos") or []) if not r.get("fork")]
        repos.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)
        for repo in repos[:max_repos_per_person]:
            full_name = repo.get("full_name")
            if not full_name:
                continue
            try:
                contributors = connector.get_json(
                    f"https://api.github.com/repos/{full_name}/contributors",
                    params={"per_page": max_contributors_per_repo},
                )
            except Exception:
                continue  # private/blocked/rate issues: skip repo, keep going
            for contributor in contributors:
                login = contributor.get("login")
                if not login or login == record.external_id or contributor.get("type") == "Bot":
                    continue
                reason = (
                    f"contributor ({contributor.get('contributions', '?')} commits) "
                    f"to {full_name}"
                )
                if _add_lead(session, "github", login, record, reason):
                    added += 1
    session.commit()
    return added


def drain_leads(
    session: Session, limit: int = 25, source: str | None = None,
    enrich_chain: bool = False,
) -> tuple[int, int]:
    """Ingest pending leads. Returns (ingested, failed)."""
    stmt = (
        select(DiscoveryLead)
        .where(DiscoveryLead.status == "pending")
        .order_by(DiscoveryLead.created_at)
        .limit(limit)
    )
    if source:
        stmt = stmt.where(DiscoveryLead.source == source)
    leads = session.execute(stmt).scalars().all()
    connectors: dict = {}
    ok = failed = 0
    for lead in leads:
        connectors.setdefault(lead.source, get_connector(lead.source))
        try:
            run_connector(
                session, connectors[lead.source], lead.identifier, enrich_chain=enrich_chain
            )
            lead.status = "ingested"
            ok += 1
        except Exception as exc:
            lead.status = "error"
            failed += 1
            print(f"lead failed {lead.source}:{lead.identifier}: {exc}")
        session.commit()
    return ok, failed
