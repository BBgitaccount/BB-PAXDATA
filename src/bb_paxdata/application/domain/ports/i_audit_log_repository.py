"""Port interface for Audit Log repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from bb_paxdata.application.domain.models.audit_log import (
    AuditLogEntry,
    AuditLogVerificationResult,
)


class IAuditLogRepository(Protocol):
    """Repository interface for immutable audit log with hash chain verification."""

    async def save(self, entry: AuditLogEntry) -> AuditLogEntry:
        """Save a new audit log entry with hash chain linking."""
        ...

    async def get_by_id(self, entry_id: str) -> AuditLogEntry | None:
        """Retrieve an audit log entry by ID."""
        ...

    async def get_by_correlation_id(
        self, correlation_id: str
    ) -> Sequence[AuditLogEntry]:
        """Retrieve all audit log entries for a correlation ID."""
        ...

    async def search(
        self,
        actor_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[AuditLogEntry]:
        """Search audit log entries with filters."""
        ...

    async def verify_chain_integrity(
        self, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> AuditLogVerificationResult:
        """Verify the integrity of the hash chain for entries in the date range."""
        ...

    async def get_latest_hash(self) -> str | None:
        """Get the hash of the most recent audit log entry."""
        ...
