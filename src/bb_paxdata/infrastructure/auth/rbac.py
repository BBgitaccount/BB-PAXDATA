"""RBAC (Role-Based Access Control) for HITL formula validation."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.repositories.reviewer_assignment import (
    ReviewerAssignmentRepository,
)


async def check_formula_permission(
    reviewer_id: str,
    required_level: str,
    scope_type: str | None,
    scope_value: str | None,
    session: AsyncSession,
) -> bool:
    """Check if a reviewer has the required permission for a given scope.

    Uses ReviewerAssignmentRepository to query the database.

    Args:
        reviewer_id: Unique reviewer identifier.
        required_level: Required permission level (e.g., 'verdict', 'correct', 'admin').
        scope_type: Type of scope (e.g., 'formula', 'country', 'global').
        scope_value: Value of scope (e.g., 'hedging_score', 'TR').
        session: SQLAlchemy async session.

    Returns:
        True if permission is granted.

    Raises:
        PermissionError: If permission is denied.
    """
    repo = ReviewerAssignmentRepository(session)
    has_permission = await repo.check_permission(
        reviewer_id=reviewer_id,
        required_level=required_level,
        scope_type=scope_type,
        scope_value=scope_value,
    )

    if not has_permission:
        raise PermissionError(
            f"Reviewer '{reviewer_id}' does not have '{required_level}' permission "
            f"for scope {scope_type}={scope_value}"
        )

    return True
