from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

STAGES = [
    "new",
    "contacted",
    "qualified",
    "meeting_scheduled",
    "proposal",
    "won",
    "lost",
]

ACTIVITY_TYPES = [
    "created",
    "email_ingested",
    "stage_changed",
    "meeting_scheduled",
    "note",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Base):
    __tablename__ = "leads"
    # Email is the ingestion dedupe key, so duplicates must be impossible at
    # the DB level — but manual leads may have no email yet, hence partial.
    __table_args__ = (
        Index(
            "uq_leads_email_nonblank",
            "email",
            unique=True,
            sqlite_where=text("email != ''"),
            postgresql_where=text("email != ''"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), index=True, default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(100), default="manual")
    stage: Mapped[str] = mapped_column(String(30), default="new", index=True)
    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    emails: Mapped[list["EmailMessage"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    meetings: Mapped[list["Meeting"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Activity.created_at.desc()",
    )


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    subject: Mapped[str] = mapped_column(String(500), default="")
    sender: Mapped[str] = mapped_column(String(320), default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw_body: Mapped[str] = mapped_column(Text, default="")
    extraction_json: Mapped[str] = mapped_column(Text, default="{}")
    extraction_method: Mapped[str] = mapped_column(String(20), default="fallback")
    message_id: Mapped[str] = mapped_column(String(500), default="", index=True)
    mailbox: Mapped[str] = mapped_column(String(320), default="")

    lead: Mapped[Lead] = relationship(back_populates="emails")


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lead: Mapped[Lead] = relationship(back_populates="meetings")


class GmailAccount(Base):
    """A Gmail mailbox connected via OAuth; the refresh token lets the
    poller mint access tokens indefinitely until the user disconnects."""

    __tablename__ = "gmail_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    refresh_token: Mapped[str] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lead: Mapped[Lead] = relationship(back_populates="activities")
