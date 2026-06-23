"""Repository implementation for Audit Log with hash chain verification."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.audit_log import (
    AuditLogEntry,
    AuditLogVerificationResult,
)
from bb_paxdata.application.domain.ports.i_audit_log_repository import (
    IAuditLogRepository,
)
from bb_paxdata.infrastructure.db.audit_log_table import AuditLogORM


class AuditLogRepository(IAuditLogRepository):
    """Repository for immutable audit log with hash chain verification."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, entry: AuditLogEntry) -> AuditLogEntry:
        """
        Save a new audit log entry with hash chain linking.

        Automatically computes the entry's hash and links it to the previous entry.
        """
        # Get the hash of the most recent entry
        previous_hash = await self.get_latest_hash()

        # Compute this entry's hash
        entry.compute_entry_hash()

        # Link to previous entry
        entry.hash_chain = previous_hash

        # Create ORM instance
        orm = AuditLogORM.from_domain_model(entry)

        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)

        return orm.to_domain_model()

    async def get_by_id(self, entry_id: str) -> AuditLogEntry | None:
        """Retrieve an audit log entry by ID."""
        stmt = select(AuditLogORM).where(AuditLogORM.id == entry_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()

        if orm:
            return orm.to_domain_model()
        return None

    async def get_by_correlation_id(
        self, correlation_id: str
    ) -> Sequence[AuditLogEntry]:
        """Retrieve all audit log entries for a correlation ID."""
        stmt = (
            select(AuditLogORM)
            .where(AuditLogORM.correlation_id == correlation_id)
            .order_by(AuditLogORM.timestamp)
        )
        result = await self._session.execute(stmt)
        orms = result.scalars().all()

        return [orm.to_domain_model() for orm in orms]

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
        conditions = []

        if actor_id:
            conditions.append(AuditLogORM.actor_id == actor_id)
        if action:
            conditions.append(AuditLogORM.action == action)
        if resource_type:
            conditions.append(AuditLogORM.resource_type == resource_type)
        if resource_id:
            conditions.append(AuditLogORM.resource_id == resource_id)
        if start_date:
            conditions.append(AuditLogORM.timestamp >= start_date)
        if end_date:
            conditions.append(AuditLogORM.timestamp <= end_date)

        stmt = (
            select(AuditLogORM)
            .where(and_(*conditions) if conditions else True)
            .order_by(AuditLogORM.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(stmt)
        orms = result.scalars().all()

        return [orm.to_domain_model() for orm in orms]

    async def verify_chain_integrity(
        self, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> AuditLogVerificationResult:
        """
        Verify the integrity of the hash chain for entries in the date range.

        Checks that each entry's hash_chain field matches the computed hash
        of the previous entry in chronological order.
        """
        conditions = []

        if start_date:
            conditions.append(AuditLogORM.timestamp >= start_date)
        if end_date:
            conditions.append(AuditLogORM.timestamp <= end_date)

        stmt = (
            select(AuditLogORM)
            .where(and_(*conditions) if conditions else True)
            .order_by(AuditLogORM.timestamp)
        )

        result = await self._session.execute(stmt)
        orms = result.scalars().all()

        entries = [orm.to_domain_model() for orm in orms]
        total_entries = len(entries)
        violations = []

        previous_hash = None
        verified_count = 0

        for idx, entry in enumerate(entries):
            # Verify the entry's hash_chain matches the previous entry's hash
            if not entry.verify_chain_integrity(previous_hash):
                violation = {
                    "index": idx,
                    "entry_id": entry.id,
                    "expected_hash": previous_hash,
                    "actual_hash": entry.hash_chain,
                    "timestamp": entry.timestamp.isoformat(),
                }
                violations.append(violation)

                # Return early on first violation if needed
                if not violations:
                    return AuditLogVerificationResult(
                        is_valid=False,
                        total_entries=total_entries,
                        verified_entries=verified_count,
                        first_violation_index=idx,
                        first_violation_details=str(violation),
                        violations=violations,
                    )
            else:
                verified_count += 1

            # Update previous_hash to this entry's computed hash
            previous_hash = entry.compute_entry_hash()

        is_valid = len(violations) == 0

        return AuditLogVerificationResult(
            is_valid=is_valid,
            total_entries=total_entries,
            verified_entries=verified_count,
            violations=violations,
            first_violation_index=violations[0]["index"] if violations else None,
            first_violation_details=str(violations[0]) if violations else None,
        )

    async def get_latest_hash(self) -> str | None:
        """Get the hash of the most recent audit log entry."""
        stmt = select(AuditLogORM).order_by(AuditLogORM.timestamp.desc()).limit(1)

        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()

        if orm:
            entry = orm.to_domain_model()
            return entry.compute_entry_hash()
        return None
