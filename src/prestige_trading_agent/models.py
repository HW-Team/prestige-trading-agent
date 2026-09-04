from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prestige_trading_agent.db import Base
from prestige_trading_agent.domain import AccessStatus, FunnelPath, FunnelState, OutboxKind


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    consent: Mapped[bool] = mapped_column(Boolean, default=True)


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("source", "source_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    source: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[str] = mapped_column(String(255))
    path: Mapped[FunnelPath] = mapped_column(
        Enum(FunnelPath, native_enum=False), default=FunnelPath.UNKNOWN
    )
    state: Mapped[FunnelState] = mapped_column(
        Enum(FunnelState, native_enum=False), default=FunnelState.NEW
    )
    contact: Mapped[Contact] = relationship()


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("channel", "external_thread_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    external_thread_id: Mapped[str] = mapped_column(String(255))
    state: Mapped[FunnelState] = mapped_column(
        Enum(FunnelState, native_enum=False), default=FunnelState.NEW
    )


class Message(TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("channel", "external_message_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    external_message_id: Mapped[str] = mapped_column(String(255))
    direction: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)


class FormSubmission(TimestampMixin, Base):
    __tablename__ = "form_submissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(String(255), unique=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    path: Mapped[FunnelPath] = mapped_column(Enum(FunnelPath, native_enum=False))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider_subscription_id: Mapped[str] = mapped_column(String(255), unique=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    product: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50))


class WebhookEvent(TimestampMixin, Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(30))
    event_id: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccessRequest(TimestampMixin, Base):
    __tablename__ = "access_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)
    product: Mapped[str] = mapped_column(String(100), default="tradingview_indicator")
    status: Mapped[AccessStatus] = mapped_column(
        Enum(AccessStatus, native_enum=False), default=AccessStatus.PENDING
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)


class OutboxJob(TimestampMixin, Base):
    __tablename__ = "outbox_jobs"
    __table_args__ = (Index("ix_outbox_pending", "processed_at", "available_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True)
    kind: Mapped[OutboxKind] = mapped_column(Enum(OutboxKind, native_enum=False))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class Feedback(TimestampMixin, Base):
    """Tester feedback on a single agent reply (test console capture)."""

    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    rating: Mapped[str] = mapped_column(String(20))  # e.g. "good" | "bad" | "needs_work"
    comment: Mapped[str | None] = mapped_column(Text)
    tester: Mapped[str | None] = mapped_column(String(255))
    last_error: Mapped[str | None] = mapped_column(Text)
