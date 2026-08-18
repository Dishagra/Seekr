"""SQLAlchemy models.

Design principles:
- Source records are immutable-ish raw captures; they are never destroyed
  by entity resolution or merging.
- Every derived attribute is backed by an Evidence row pointing at the
  source record it came from.
- Conflicting values coexist as separate Evidence rows; nothing is
  silently overwritten.
- Person.id is a stable UUID the downstream ranking tool can reference.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Person(Base):
    __tablename__ = "person"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    canonical_name: Mapped[str | None] = mapped_column(String(255), index=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    location: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(2), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    current_role: Mapped[str | None] = mapped_column(String(255))
    current_organization: Mapped[str | None] = mapped_column(String(255))
    profile_urls: Mapped[list] = mapped_column(JSON, default=list)
    # tombstone: set when this person was merged into another; the ID stays
    # resolvable so downstream references never break
    merged_into: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    identities: Mapped[list["IdentityLink"]] = relationship(back_populates="person")
    keys: Mapped[list["PersonKey"]] = relationship(back_populates="person")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="person")
    affiliations: Mapped[list["Affiliation"]] = relationship(back_populates="person")
    authorships: Mapped[list["Authorship"]] = relationship(back_populates="person")
    contributions: Mapped[list["Contribution"]] = relationship(back_populates="person")


class SourceRecord(Base):
    """One raw capture of one external profile/page. Never deleted on merge."""

    __tablename__ = "source_record"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "github", "openalex"
    source_type: Mapped[str] = mapped_column(String(64))  # e.g. "code_hosting", "scholarly"
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(1024))
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    first_observed: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_observed: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime)

    identity: Mapped["IdentityLink | None"] = relationship(back_populates="source_record")


class IdentityLink(Base):
    """Resolution decision: this source record belongs to this person."""

    __tablename__ = "identity_link"
    __table_args__ = (UniqueConstraint("source_record_id", name="uq_identity_source_record"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    source_record_id: Mapped[int] = mapped_column(ForeignKey("source_record.id"))
    match_method: Mapped[str] = mapped_column(String(64))  # "new" | "strong:<key>" | "fuzzy:name+org"
    match_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    matched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    review_state: Mapped[str] = mapped_column(String(32), default="unreviewed")
    # "unreviewed" | "approved" | "split"

    person: Mapped[Person] = relationship(back_populates="identities")
    source_record: Mapped[SourceRecord] = relationship(back_populates="identity")


class PersonKey(Base):
    """Strong identifiers used for deterministic entity resolution."""

    __tablename__ = "person_key"
    __table_args__ = (UniqueConstraint("key_type", "key_value", name="uq_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    key_type: Mapped[str] = mapped_column(String(32))  # "orcid" | "email" | "url" | "username"
    key_value: Mapped[str] = mapped_column(String(512))
    source_record_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))

    person: Mapped[Person] = relationship(back_populates="keys")


class Evidence(Base):
    """Evidence backing one attribute claim about one person."""

    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint(
            "person_id", "attribute_type", "value", "source_record_id", name="uq_evidence"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    attribute_type: Mapped[str] = mapped_column(String(64), index=True)
    # e.g. "skill", "role", "education", "location", "research_interest", "specialization"
    value: Mapped[str] = mapped_column(String(512), index=True)
    extracted_info: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(1024))
    source_record_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    verification_state: Mapped[str] = mapped_column(String(32), default="unverified")
    # "unverified" | "corroborated" | "conflicted" | "verified"

    person: Mapped[Person] = relationship(back_populates="evidence")


class Organization(Base):
    __tablename__ = "organization"
    __table_args__ = (UniqueConstraint("name", name="uq_org_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    org_type: Mapped[str | None] = mapped_column(String(64))  # "company" | "university" | ...
    website: Mapped[str | None] = mapped_column(String(1024))
    location: Mapped[str | None] = mapped_column(String(255))

    affiliations: Mapped[list["Affiliation"]] = relationship(back_populates="organization")


class Affiliation(Base):
    """Person -> worked_at / studied_at -> Organization."""

    __tablename__ = "affiliation"
    __table_args__ = (
        UniqueConstraint(
            "person_id", "organization_id", "role", "relation", name="uq_affiliation"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), index=True)
    relation: Mapped[str] = mapped_column(String(32), default="worked_at")  # or "studied_at"
    role: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[str | None] = mapped_column(String(32))
    end_date: Mapped[str | None] = mapped_column(String(32))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    source_record_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))
    url: Mapped[str | None] = mapped_column(String(1024))

    person: Mapped[Person] = relationship(back_populates="affiliations")
    organization: Mapped[Organization] = relationship(back_populates="affiliations")


class Publication(Base):
    __tablename__ = "publication"
    __table_args__ = (UniqueConstraint("external_id", name="uq_pub_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(255))  # DOI or source id
    title: Mapped[str] = mapped_column(String(1024), index=True)
    venue: Mapped[str | None] = mapped_column(String(512))
    published_date: Mapped[str | None] = mapped_column(String(32))
    url: Mapped[str | None] = mapped_column(String(1024))
    doi: Mapped[str | None] = mapped_column(String(255), index=True)
    citations: Mapped[int | None] = mapped_column(Integer)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    raw_authors: Mapped[list] = mapped_column(JSON, default=list)
    source_record_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))

    authorships: Mapped[list["Authorship"]] = relationship(back_populates="publication")


class Authorship(Base):
    """Person -> authored -> Publication."""

    __tablename__ = "authorship"
    __table_args__ = (UniqueConstraint("person_id", "publication_id", name="uq_authorship"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publication.id"), index=True)
    author_position: Mapped[int | None] = mapped_column(Integer)

    person: Mapped[Person] = relationship(back_populates="authorships")
    publication: Mapped[Publication] = relationship(back_populates="authorships")


class Project(Base):
    __tablename__ = "project"
    __table_args__ = (UniqueConstraint("url", name="uq_project_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1024))
    technologies: Mapped[list] = mapped_column(JSON, default=list)
    organization: Mapped[str | None] = mapped_column(String(255))
    activity: Mapped[dict] = mapped_column(JSON, default=dict)  # stars, forks, commit counts...
    started_at: Mapped[str | None] = mapped_column(String(32))
    last_active_at: Mapped[str | None] = mapped_column(String(32))
    source_record_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))

    contributions: Mapped[list["Contribution"]] = relationship(back_populates="project")


class Contribution(Base):
    """Person -> contributed_to -> Project."""

    __tablename__ = "contribution"
    __table_args__ = (UniqueConstraint("person_id", "project_id", name="uq_contribution"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(64))  # "owner" | "contributor"

    person: Mapped[Person] = relationship(back_populates="contributions")
    project: Mapped[Project] = relationship(back_populates="contributions")


class ChangeLog(Base):
    """Field-level change history for incremental sync by the ranking tool."""

    __tablename__ = "change_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    field: Mapped[str] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    source_record_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PersonNameToken(Base):
    """Blocking index for entity resolution: one row per (person, name token).

    Lets fuzzy matching enumerate a small candidate set by shared name token
    instead of scanning every person.
    """

    __tablename__ = "person_name_token"
    __table_args__ = (UniqueConstraint("person_id", "token", name="uq_person_name_token"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    token: Mapped[str] = mapped_column(String(128), index=True)


class AttributeConflict(Base):
    """Two sources disagreeing about one attribute, stored as a first-class
    object with BOTH sides' provenance — a durable item a human can review,
    not just a log line."""

    __tablename__ = "attribute_conflict"
    __table_args__ = (
        UniqueConstraint(
            "person_id", "attribute_name", "value_a", "value_b", name="uq_attr_conflict"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    attribute_name: Mapped[str] = mapped_column(String(64), index=True)
    value_a: Mapped[str] = mapped_column(String(512))
    source_a: Mapped[str | None] = mapped_column(String(64))
    source_record_a_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))
    value_b: Mapped[str] = mapped_column(String(512))
    source_b: Mapped[str | None] = mapped_column(String(64))
    source_record_b_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    # "active" | "resolved" | "superseded"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MergeCandidate(Base):
    """Near-miss resolution: two persons that might be the same, queued for
    human review instead of auto-merged. Approving merges them; rejecting
    records the decision so the pair is not re-proposed."""

    __tablename__ = "merge_candidate"
    __table_args__ = (
        UniqueConstraint("person_id", "candidate_person_id", name="uq_merge_candidate"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    candidate_person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # "pending" | "merged" | "rejected"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DiscoveryLead(Base):
    """A person spotted in existing data but not yet ingested (co-author,
    repo contributor, org member, ...). Drained by `rip.cli ingest-leads`."""

    __tablename__ = "discovery_lead"
    __table_args__ = (UniqueConstraint("source", "identifier", name="uq_lead"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    identifier: Mapped[str] = mapped_column(String(255))
    discovered_via_record_id: Mapped[int | None] = mapped_column(ForeignKey("source_record.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # "pending" | "ingested" | "error" | "skipped"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WebhookSubscription(Base):
    """A downstream system asking to be pushed change events."""

    __tablename__ = "webhook_subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(1024))
    event_types: Mapped[list] = mapped_column(JSON, default=list)
    signing_secret: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WebhookDelivery(Base):
    """One queued push. Written in the ingest transaction, sent later by
    `rip.cli deliver-webhooks` — an outbox, so a subscriber never hears about
    a change that was rolled back."""

    __tablename__ = "webhook_delivery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("webhook_subscription.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # "pending" | "delivered" | "failed"
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)


class IngestionRun(Base):
    """Source health / failure tracking."""

    __tablename__ = "ingestion_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    identifier: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|ok|error|skipped
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
