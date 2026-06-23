"""
SQLAlchemy ORM model for Audit Log table.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.audit_log import AuditLogEntry


class AuditLogORM(Base):
    """
    Immutable audit log entry with hash chain verification.

    Each entry references the previous entry's hash to create a tamper-evident chain.
    """

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hash_chain: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    def to_domain_model(self):
        """Convert ORM to domain model."""
        from bb_paxdata.application.domain.models.audit_log import AuditLogEntry

        return AuditLogEntry(  # type: ignore[arg-type]
            id=self.id,
            timestamp=self.timestamp,
            actor_id=self.actor_id,
            action=self.action,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            before_state=self.before_state,
            after_state=self.after_state,
            correlation_id=self.correlation_id,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            hash_chain=self.hash_chain,
        )

    @classmethod
    def from_domain_model(cls, entry: AuditLogEntry) -> AuditLogORM:
        """Create ORM instance from domain model."""
        return cls(
            id=entry.id,
            timestamp=entry.timestamp,
            actor_id=entry.actor_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            before_state=entry.before_state,
            after_state=entry.after_state,
            correlation_id=entry.correlation_id,
            ip_address=entry.ip_address,
            user_agent=entry.user_agent,
            hash_chain=entry.hash_chain,
        )


# Composite indexes for common query patterns
__table_args__ = (
    Index("idx_audit_resource", "resource_type", "resource_id"),
    Index("idx_audit_actor_action", "actor_id", "action"),
    Index("idx_audit_timestamp_action", "timestamp", "action"),
)
