"""Repository for FormulaValidationAudit — WORM (Write Once Read Many).

This repository only supports create and read operations.
Records are NEVER deleted or updated after creation.
"""

from __future__ import annotations

from sqlalchemy import select, update

from bb_paxdata.infrastructure.db.models import FormulaValidationAudit
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository


class FormulaAuditRepository(BaseRepository[FormulaValidationAudit]):
    """Immutable audit trail repository. No delete/update on records."""

    model_class = FormulaValidationAudit

    async def create_audit_entry(
        self,
        *,
        log_id: int,
        action_type: str,
        performed_by: str,
        previous_verdict: str | None = None,
        new_verdict: str | None = None,
        previous_value: float | None = None,
        new_value: float | None = None,
        ip_address: str | None = None,
        justification: str | None = None,
        review_status: str | None = None,
    ) -> FormulaValidationAudit:
        """Create a new immutable audit entry."""
        entry = FormulaValidationAudit(
            log_id=log_id,
            action_type=action_type,
            performed_by=performed_by,
            previous_verdict=previous_verdict,
            new_verdict=new_verdict,
            previous_value=previous_value,
            new_value=new_value,
            ip_address=ip_address,
            justification=justification,
            review_status=review_status,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def get_by_log_id(self, log_id: int) -> list[FormulaValidationAudit]:
        """Get all audit entries for a specific log_id, ordered chronologically."""
        stmt = (
            select(FormulaValidationAudit)
            .where(FormulaValidationAudit.log_id == log_id)
            .order_by(FormulaValidationAudit.performed_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_second_reviews(self) -> list[FormulaValidationAudit]:
        """Get audit entries requiring second-eye approval."""
        stmt = (
            select(FormulaValidationAudit)
            .where(FormulaValidationAudit.review_status == "PENDING")
            .order_by(FormulaValidationAudit.performed_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def approve_second_review(
        self, audit_id: int, reviewed_by: str
    ) -> FormulaValidationAudit | None:
        """Approve a pending second-eye review.

        Note: This is the ONLY update allowed on audit entries —
        it only sets review_status from PENDING to APPROVED.
        """
        stmt = (
            update(FormulaValidationAudit)
            .where(
                FormulaValidationAudit.audit_id == audit_id,
                FormulaValidationAudit.review_status == "PENDING",
            )
            .values(review_status="APPROVED", reviewed_by=reviewed_by)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return await self.get_by_id(audit_id)
