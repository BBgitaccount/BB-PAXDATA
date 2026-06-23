"""Celery tasks for async audit log processing."""

from __future__ import annotations

from typing import Any

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.services.audit_log_service import AuditLogService
from bb_paxdata.infrastructure.db.repositories.audit_log_repository import (
    AuditLogRepository,
)
from bb_paxdata.infrastructure.tasks.celery_app import get_celery_app

celery_app = get_celery_app()


class AuditLogTask(Task):
    """Base task with database session management."""

    _db: AsyncSession | None = None

    @property
    def db(self) -> AsyncSession:
        """Lazy initialization of database session."""
        if self._db is None:
            from bb_paxdata.infrastructure.db.session import async_session_maker

            self._db = async_session_maker()
        return self._db

    def after_return(self, *args: Any, **kwargs: Any) -> None:
        """Clean up database session after task completion."""
        if self._db is not None:
            import asyncio

            asyncio.run(self._db.close())
            self._db = None


@celery_app.task(
    base=AuditLogTask,
    name="bb_paxdata.infrastructure.tasks.audit_tasks.log_domain_event",
    bind=True,
)
def log_domain_event(
    self,
    event: dict,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """
    Async task to convert and log a domain event as an audit log entry.

    Args:
        event: Domain event dictionary
        ip_address: Optional IP address from request context
        user_agent: Optional user agent from request context

    Returns:
        Dict with audit entry ID and status
    """
    import asyncio

    # Convert domain event to audit entry
    audit_entry = AuditLogService.domain_event_to_audit_entry(
        event, ip_address=ip_address, user_agent=user_agent
    )

    # Save to database
    async def _save() -> dict:
        repo = AuditLogRepository(self.db)
        saved_entry = await repo.save(audit_entry)
        await self.db.commit()
        return {
            "status": "success",
            "audit_entry_id": saved_entry.id,
            "timestamp": saved_entry.timestamp.isoformat(),
        }

    return asyncio.run(_save())


@celery_app.task(
    base=AuditLogTask,
    name="bb_paxdata.infrastructure.tasks.audit_tasks.log_domain_event_batch",
    bind=True,
)
def log_domain_event_batch(
    self,
    events: list[dict],
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """
    Async task to batch convert and log multiple domain events as audit log entries.

    Args:
        events: List of domain event dictionaries
        ip_address: Optional IP address from request context
        user_agent: Optional user agent from request context

    Returns:
        Dict with batch processing results
    """
    import asyncio

    async def _save_batch() -> dict:
        repo = AuditLogRepository(self.db)
        results = []

        for event in events:
            audit_entry = AuditLogService.domain_event_to_audit_entry(
                event, ip_address=ip_address, user_agent=user_agent
            )
            saved_entry = await repo.save(audit_entry)
            results.append(
                {
                    "audit_entry_id": saved_entry.id,
                    "timestamp": saved_entry.timestamp.isoformat(),
                }
            )

        await self.db.commit()

        return {
            "status": "success",
            "total_processed": len(results),
            "entries": results,
        }

    return asyncio.run(_save_batch())
