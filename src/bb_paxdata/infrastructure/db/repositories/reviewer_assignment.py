"""Repository for ReviewerAssignment — RBAC & workload balancing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select, update

from bb_paxdata.infrastructure.db.models import ReviewerAssignment
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository

# Permission level hierarchy (higher includes all lower)
_PERMISSION_HIERARCHY = {
    "view": 0,
    "verdict": 1,
    "correct": 2,
    "escalate": 3,
    "admin": 4,
}


class ReviewerAssignmentRepository(BaseRepository[ReviewerAssignment]):
    """RBAC repository for reviewer assignments and workload tracking."""

    model_class = ReviewerAssignment

    async def check_permission(
        self,
        reviewer_id: str,
        required_level: str,
        scope_type: str | None = None,
        scope_value: str | None = None,
    ) -> bool:
        """Check if a reviewer has the required permission level.

        Checks in order:
        1. Exact scope match (e.g., formula=hedging_score)
        2. Global scope (covers everything)

        Returns True if permission is granted.
        """
        required_rank = _PERMISSION_HIERARCHY.get(required_level, 0)

        # Build query for matching assignments
        conditions = [
            ReviewerAssignment.reviewer_id == reviewer_id,
            ReviewerAssignment.is_active == True,  # noqa: E712
        ]

        if scope_type and scope_value:
            # Check both exact scope AND global scope
            stmt = select(ReviewerAssignment).where(
                and_(
                    *conditions,
                    ReviewerAssignment.scope_type.in_([scope_type, "global"]),
                )
            )
        else:
            stmt = select(ReviewerAssignment).where(and_(*conditions))

        result = await self._session.execute(stmt)
        assignments: list[ReviewerAssignment] = list(result.scalars().all())

        for assignment in assignments:
            # Global scope covers everything
            if assignment.scope_type == "global":
                rank = _PERMISSION_HIERARCHY.get(assignment.permission_level, 0)
                if rank >= required_rank:
                    return True

            # Exact scope match
            if (
                assignment.scope_type == scope_type
                and assignment.scope_value == scope_value
            ):
                rank = _PERMISSION_HIERARCHY.get(assignment.permission_level, 0)
                if rank >= required_rank:
                    return True

        return False

    async def get_daily_count(self, reviewer_id: str) -> int:
        """Get today's review count for a reviewer."""
        stmt = select(func.sum(ReviewerAssignment.current_daily_count)).where(
            ReviewerAssignment.reviewer_id == reviewer_id,
            ReviewerAssignment.is_active == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def increment_daily_count(self, reviewer_id: str) -> None:
        """Increment the daily review count for a reviewer (all assignments)."""
        stmt = (
            update(ReviewerAssignment)
            .where(
                ReviewerAssignment.reviewer_id == reviewer_id,
                ReviewerAssignment.is_active == True,  # noqa: E712
            )
            .values(
                current_daily_count=ReviewerAssignment.current_daily_count + 1,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def reset_daily_counts(self) -> int:
        """Reset all daily counts to 0. Run once per day (midnight cron)."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = (
            update(ReviewerAssignment)
            .where(ReviewerAssignment.is_active == True)  # noqa: E712
            .values(current_daily_count=0, last_reset_at=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        res_any: Any = result
        return int(res_any.rowcount or 0)

    async def get_workload_balanced_reviewer(
        self,
        scope_type: str,
        scope_value: str,
        required_level: str = "verdict",
    ) -> str | None:
        """Find the reviewer with the lowest daily count for a given scope.

        Returns reviewer_id or None if no eligible reviewer found.
        """
        required_rank = _PERMISSION_HIERARCHY.get(required_level, 0)

        stmt = (
            select(ReviewerAssignment)
            .where(
                ReviewerAssignment.is_active == True,  # noqa: E712
                ReviewerAssignment.scope_type.in_([scope_type, "global"]),
                ReviewerAssignment.current_daily_count
                < ReviewerAssignment.max_daily_reviews,
            )
            .order_by(ReviewerAssignment.current_daily_count.asc())
        )

        if scope_type != "global":
            stmt = stmt.where(
                ReviewerAssignment.scope_value.in_([scope_value, "global"])
            )

        result = await self._session.execute(stmt)
        assignments: list[ReviewerAssignment] = list(result.scalars().all())

        for assignment in assignments:
            rank = _PERMISSION_HIERARCHY.get(assignment.permission_level, 0)
            if rank >= required_rank:
                reviewer_id = assignment.reviewer_id
                assert isinstance(reviewer_id, str)
                return reviewer_id

        return None

    async def seed_default_assignments(self) -> list[ReviewerAssignment]:
        """Create default RBAC assignments for development/testing.

        Creates a global admin and a global analyst.
        """
        defaults = [
            ReviewerAssignment(
                reviewer_id="admin@paxdata.local",
                scope_type="global",
                scope_value="global",
                permission_level="admin",
                max_daily_reviews=100,
            ),
            ReviewerAssignment(
                reviewer_id="analyst@paxdata.local",
                scope_type="global",
                scope_value="global",
                permission_level="verdict",
                max_daily_reviews=50,
            ),
        ]

        created: list[ReviewerAssignment] = []
        for assignment in defaults:
            # Check if already exists
            existing = await self._session.execute(
                select(ReviewerAssignment).where(
                    ReviewerAssignment.reviewer_id == assignment.reviewer_id,
                    ReviewerAssignment.scope_type == assignment.scope_type,
                    ReviewerAssignment.scope_value == assignment.scope_value,
                )
            )
            if existing.scalar_one_or_none() is None:
                self._session.add(assignment)
                created.append(assignment)

        if created:
            await self._session.flush()
        return created
