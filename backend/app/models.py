"""Versioned typed resources share ownership and CAS storage; references are relational."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, JSON, ForeignKey, UniqueConstraint, Index, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(300))
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
class Login(Base):
    __tablename__ = "logins"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[str] = mapped_column(String(40))
class OAuthState(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(64))
    expires: Mapped[str] = mapped_column(String(40))
class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (Index("resources_owner_kind", "user_id", "kind"),)
class Link(Base):
    __tablename__ = "links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(32))
    __table_args__ = (UniqueConstraint("source_id", "target_id", "relation"),)
class Idempotency(Base):
    __tablename__ = "idempotency"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(200))
    scope: Mapped[str] = mapped_column(String(200))
    digest: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("user_id", "key", "scope"),)
class Counter(Base):
    __tablename__ = "counters"
    key: Mapped[str] = mapped_column(String(150), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
class StreamEvent(Base):
    __tablename__ = "stream_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[str] = mapped_column(String(40), default=now)
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)
class SearchDocument(Base):
    __tablename__ = "search_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    source_version: Mapped[int] = mapped_column(Integer)
    identity: Mapped[str] = mapped_column(String(300))
    embedding: Mapped[list] = mapped_column(JSON().with_variant(Vector(), "postgresql"))
    context: Mapped[dict] = mapped_column(JSON)
class DeletionLedger(Base):
    __tablename__ = "deletion_ledger"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    deleted_at: Mapped[str] = mapped_column(String(40), default=now)
    completed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
