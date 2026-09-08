"""SQLAlchemy 2.0 ORM models (declarative base).

Four tables: Target, ContentHash, AuthCredential, PollLog.
"""

from datetime import datetime

from sqlalchemy import (
    Index,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base for all ORM models."""
    pass


class Target(Base):
    """Monitored target account on a platform."""

    __tablename__ = "target"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)
    target_username: Mapped[str] = mapped_column(String(255), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    added_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_poll_pk: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    content_hashes = relationship("ContentHash", back_populates="target", lazy="selectin")
    poll_logs = relationship("PollLog", back_populates="target", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("platform", "target_id", "content_type", name="uq_target_platform_id_type"),
        Index("ix_target_platform_active", "platform", "content_type", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Target(id={self.id}, platform={self.platform}, username={self.target_username}, type={self.content_type})>"


class ContentHash(Base):
    """Idempotent deduplication key for delivered content."""

    __tablename__ = "content_hash"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("target.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    content_pk: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(10), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    media_urls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    telegram_msg_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    target = relationship("Target", back_populates="content_hashes")

    __table_args__ = (
        UniqueConstraint("target_id", "content_hash", name="uq_content_hash_target_hash"),
        UniqueConstraint("platform", "content_pk", name="uq_content_hash_platform_pk"),
        Index("ix_content_hash_target_delivered", "target_id", "delivered_at"),
        Index("ix_content_hash_delivered_at", "delivered_at"),
    )

    def __repr__(self) -> str:
        return f"<ContentHash(id={self.id}, platform={self.platform}, pk={self.content_pk})>"


class AuthCredential(Base):
    """Platform authentication credentials."""

    __tablename__ = "auth_credential"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credential_data: Mapped[str] = mapped_column(Text, nullable=False)
    file_data: Mapped[bytes | None] = mapped_column(nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    added_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_auth_platform_valid", "platform", "is_valid"),
    )

    def __repr__(self) -> str:
        return f"<AuthCredential(id={self.id}, platform={self.platform}, type={self.credential_type}, valid={self.is_valid})>"


class PollLog(Base):
    """Audit log for each polling operation."""

    __tablename__ = "poll_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("target.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    content_type: Mapped[str] = mapped_column(String(10), nullable=False)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    items_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    target = relationship("Target", back_populates="poll_logs")

    __table_args__ = (
        Index("ix_poll_log_target_started", "target_id", "started_at"),
        Index("ix_poll_log_status_started", "status", "started_at"),
        Index("ix_poll_log_job_started", "job_name", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<PollLog(id={self.id}, target={self.target_id}, status={self.status}, new={self.items_new})>"
