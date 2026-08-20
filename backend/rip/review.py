"""Merge review: surface suspicious resolution decisions, approve or split them.

Because source records are never destroyed and every merge is an IdentityLink,
a bad merge is fully reversible: `split_link` detaches one source record (and
every row it produced) into a fresh person.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    Affiliation,
    Authorship,
    ChangeLog,
    Contribution,
    Evidence,
    IdentityLink,
    MergeCandidate,
    Person,
    PersonKey,
    Publication,
    Project,
    SourceRecord,
)

MANY_LINKS_THRESHOLD = 4


def _raw_name(record: SourceRecord) -> str | None:
    """Best-effort display name straight from a source record's raw payload."""
    raw = record.raw or {}
    return (
        raw.get("name")  # dblp
        or (raw.get("author") or {}).get("display_name")  # openalex
        or (raw.get("user") or {}).get("name")  # github
        or (raw.get("user") or {}).get("display_name")  # stackoverflow
        or (raw.get("overview") or {}).get("fullname")  # huggingface
        or ((raw.get("person") or {}).get("name") or {}).get("value")  # orcid (partial)
    )


def list_suspicious(session: Session) -> dict:
    """Merges worth a human look: fuzzy matches, heavily-linked persons, key collisions."""
    fuzzy = session.execute(
        select(IdentityLink, SourceRecord, Person)
        .join(SourceRecord, SourceRecord.id == IdentityLink.source_record_id)
        .join(Person, Person.id == IdentityLink.person_id)
        .where(
            IdentityLink.match_method.like("fuzzy%"),
            IdentityLink.review_state == "unreviewed",
        )
    ).all()
    fuzzy_out = [
        {
            "link_id": link.id,
            "person_id": person.id,
            "person_name": person.canonical_name,
            "source": record.source,
            "external_id": record.external_id,
            "source_url": record.url,
            "record_name": _raw_name(record),
            "match_method": link.match_method,
            "match_confidence": link.match_confidence,
            "signals": link.signals,
        }
        for link, record, person in fuzzy
    ]

    heavy = session.execute(
        select(Person, func.count(IdentityLink.id).label("n"))
        .join(IdentityLink, IdentityLink.person_id == Person.id)
        .group_by(Person.id)
        .having(func.count(IdentityLink.id) >= MANY_LINKS_THRESHOLD)
        .order_by(func.count(IdentityLink.id).desc())
    ).all()
    heavy_out = [
        {"person_id": p.id, "person_name": p.canonical_name, "linked_sources": n}
        for p, n in heavy
    ]

    collisions = session.execute(
        select(ChangeLog).where(ChangeLog.field.like("key_collision:%"))
    ).scalars().all()
    collision_out = [
        {
            "person_id": c.person_id,
            "key": c.field.removeprefix("key_collision:"),
            "value": c.new_value,
            "other_person_id": c.old_value,
            "source_record_id": c.source_record_id,
        }
        for c in collisions
    ]

    duplicates = session.execute(
        select(MergeCandidate).where(MergeCandidate.status == "pending")
        .order_by(MergeCandidate.score.desc())
    ).scalars().all()
    duplicate_out = []
    for mc in duplicates:
        a = session.get(Person, mc.person_id)
        b = session.get(Person, mc.candidate_person_id)
        duplicate_out.append(
            {
                "candidate_id": mc.id,
                "person_id": mc.person_id,
                "person_name": a.canonical_name if a else None,
                "duplicate_person_id": mc.candidate_person_id,
                "duplicate_person_name": b.canonical_name if b else None,
                "score": mc.score,
                "signals": mc.signals,
            }
        )

    return {
        "fuzzy_merges": fuzzy_out,
        "heavily_linked_persons": heavy_out,
        "key_collisions": collision_out,
        "possible_duplicates": duplicate_out,
    }


def approve_link(session: Session, link_id: int) -> IdentityLink:
    link = session.get(IdentityLink, link_id)
    if link is None:
        raise ValueError(f"identity link {link_id} not found")
    link.review_state = "approved"
    session.commit()
    return link


def merge_persons(session: Session, keep_id: str, merge_id: str) -> Person:
    """Fold person `merge_id` into `keep_id`: move all their rows, keep both
    names as aliases, log the merge. Source records are untouched."""
    keep = session.get(Person, keep_id)
    merged = session.get(Person, merge_id)
    if keep is None or merged is None:
        raise ValueError("person not found")
    if keep_id == merge_id:
        raise ValueError("cannot merge a person into itself")

    # rows without cross-person uniqueness risk: move directly
    for model in (IdentityLink, PersonKey, Evidence):
        for row in session.execute(
            select(model).where(model.person_id == merge_id)
        ).scalars():
            row.person_id = keep_id

    # rows where the keeper may already hold an equivalent (same publication,
    # project, or affiliation): move only if absent, else drop the duplicate
    keep_pubs = {
        a.publication_id
        for a in session.execute(
            select(Authorship).where(Authorship.person_id == keep_id)
        ).scalars()
    }
    for auth in session.execute(
        select(Authorship).where(Authorship.person_id == merge_id)
    ).scalars():
        if auth.publication_id in keep_pubs:
            session.delete(auth)
        else:
            auth.person_id = keep_id
    keep_projects = {
        c.project_id
        for c in session.execute(
            select(Contribution).where(Contribution.person_id == keep_id)
        ).scalars()
    }
    for contrib in session.execute(
        select(Contribution).where(Contribution.person_id == merge_id)
    ).scalars():
        if contrib.project_id in keep_projects:
            session.delete(contrib)
        else:
            contrib.person_id = keep_id
    keep_affs = {
        (a.organization_id, a.role, a.relation)
        for a in session.execute(
            select(Affiliation).where(Affiliation.person_id == keep_id)
        ).scalars()
    }
    for aff in session.execute(
        select(Affiliation).where(Affiliation.person_id == merge_id)
    ).scalars():
        if (aff.organization_id, aff.role, aff.relation) in keep_affs:
            session.delete(aff)
        else:
            aff.person_id = keep_id
    session.flush()

    aliases = set(keep.aliases or [])
    for alias in [merged.canonical_name, *(merged.aliases or [])]:
        if alias and alias != keep.canonical_name:
            aliases.add(alias)
    keep.aliases = sorted(aliases)
    urls = set(keep.profile_urls or []) | set(merged.profile_urls or [])
    keep.profile_urls = sorted(u for u in urls if u)
    for field in ("location", "summary", "current_role", "current_organization"):
        if not getattr(keep, field) and getattr(merged, field):
            setattr(keep, field, getattr(merged, field))

    # retarget any other pending candidates that referenced the merged person
    for mc in session.execute(
        select(MergeCandidate).where(
            (MergeCandidate.person_id == merge_id)
            | (MergeCandidate.candidate_person_id == merge_id),
            MergeCandidate.status == "pending",
        )
    ).scalars():
        mc.status = "rejected" if keep_id in (mc.person_id, mc.candidate_person_id) else mc.status

    session.add(
        ChangeLog(
            person_id=keep_id,
            field="merge",
            old_value=f"person:{merge_id} ({merged.canonical_name})",
            new_value=f"person:{keep_id}",
        )
    )
    keep.updated_at = datetime.now(timezone.utc)
    # tombstone, not delete: the merged UUID stays resolvable for consumers
    merged.merged_into = keep_id
    merged.aliases = []
    merged.profile_urls = []
    session.commit()
    return keep


def resolve_duplicate(session: Session, candidate_id: int, action: str) -> dict:
    """Act on a possible-duplicate candidate: action = 'merge' or 'reject'."""
    mc = session.get(MergeCandidate, candidate_id)
    if mc is None:
        raise ValueError(f"merge candidate {candidate_id} not found")
    if mc.status != "pending":
        raise ValueError(f"candidate {candidate_id} already {mc.status}")
    if action == "merge":
        keep = merge_persons(session, mc.person_id, mc.candidate_person_id)
        mc.status = "merged"
        session.commit()
        return {"candidate_id": candidate_id, "status": "merged", "kept_person_id": keep.id}
    mc.status = "rejected"
    session.commit()
    return {"candidate_id": candidate_id, "status": "rejected"}


def split_link(session: Session, link_id: int) -> Person:
    """Detach one source record from its person into a brand-new person.

    Moves every row that record produced: keys, evidence, affiliations,
    authorships/contributions of publications/projects that record created.
    The old person keeps everything from its other sources.
    """
    link = session.get(IdentityLink, link_id)
    if link is None:
        raise ValueError(f"identity link {link_id} not found")
    record = session.get(SourceRecord, link.source_record_id)
    old_person_id = link.person_id

    new_person = Person(canonical_name=_raw_name(record), profile_urls=[record.url])
    session.add(new_person)
    session.flush()

    link.person_id = new_person.id
    link.match_method = "split:manual"
    link.match_confidence = 1.0
    link.review_state = "split"

    for model in (PersonKey, Evidence, Affiliation):
        rows = session.execute(
            select(model).where(
                model.person_id == old_person_id,
                model.source_record_id == record.id,
            )
        ).scalars().all()
        for row in rows:
            row.person_id = new_person.id

    pub_ids = session.execute(
        select(Publication.id).where(Publication.source_record_id == record.id)
    ).scalars().all()
    if pub_ids:
        for auth in session.execute(
            select(Authorship).where(
                Authorship.person_id == old_person_id,
                Authorship.publication_id.in_(pub_ids),
            )
        ).scalars():
            auth.person_id = new_person.id

    proj_ids = session.execute(
        select(Project.id).where(Project.source_record_id == record.id)
    ).scalars().all()
    if proj_ids:
        for contrib in session.execute(
            select(Contribution).where(
                Contribution.person_id == old_person_id,
                Contribution.project_id.in_(proj_ids),
            )
        ).scalars():
            contrib.person_id = new_person.id

    session.add(
        ChangeLog(
            person_id=old_person_id,
            field="split",
            old_value=f"source_record:{record.id} ({record.source}:{record.external_id})",
            new_value=f"person:{new_person.id}",
            source_record_id=record.id,
        )
    )
    new_person.updated_at = datetime.now(timezone.utc)
    session.commit()
    return new_person
