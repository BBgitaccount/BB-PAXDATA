"""Retraining Scheduler - Manages retraining job triggers.

Implements three trigger types:
1. Drift-driven (DB polling, every 15 min)
2. Manual (admin endpoint)
3. Weekly schedule (Sunday at 2:00 AM)
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class RetrainingJob(BaseModel):
    """Retraining job model."""

    id: uuid.UUID
    trigger_reason: str  # 'drift' | 'manual' | 'scheduled'
    fields: list[str]
    status: str  # 'pending' | 'running' | 'completed' | 'failed' | 'shadow_failed'
    created_at: datetime
    completed_at: datetime | None = None
    metadata: dict[str, Any] = {}


class RetrainingScheduler:
    """Manages retraining job scheduling and execution.

    Uses APScheduler for scheduled tasks.
    """

    def __init__(self, session_factory):
        """Initialize retraining scheduler.

        Args:
            session_factory: SQLAlchemy async session factory
        """
        self.session_factory = session_factory
        self.scheduler = AsyncIOScheduler()
        self._setup_scheduled_jobs()

    def _setup_scheduled_jobs(self):
        """Setup scheduled retraining jobs.

        Weekly schedule: Sunday at 2:00 AM.
        Skip condition: if a RetrainingJob with status='completed' exists in the last 7 days.
        """
        self.scheduler.add_job(
            self.run_scheduled_retraining,
            "cron",
            day_of_week="sun",
            hour=2,
            minute=0,
            id="weekly_retraining",
            replace_existing=True,
        )

    def start(self):
        """Start the scheduler."""
        self.scheduler.start()
        logger.info("retraining_scheduler_started")

    def shutdown(self):
        """Shutdown the scheduler."""
        self.scheduler.shutdown()
        logger.info("retraining_scheduler_shutdown")

    async def run_drift_triggered_retraining(self) -> RetrainingJob | None:
        """Check for drift-triggered retraining (runs every 15 min).

        Query:
        SELECT id FROM drift_alerts
        WHERE severity = 'critical'
          AND resolved = false
          AND created_at >= NOW() - INTERVAL '48h'
          AND retraining_triggered = false
        LIMIT 1

        If any row returned → insert RetrainingJob with trigger_reason='drift'
        and set drift_alerts.retraining_triggered = true.

        Returns:
            Created RetrainingJob or None
        """
        try:
            async with self.session_factory():
                # Query for untriggered critical drift alerts
                datetime.now(UTC) - timedelta(hours=48)

                # Placeholder - would query drift_alerts table
                # For now, return None
                return None

        except Exception as e:
            logger.error("drift_triggered_retraining_check_failed", error=str(e))
            return None

    async def trigger_manual_retraining(
        self, reason: str, fields: list[str]
    ) -> RetrainingJob:
        """Trigger manual retraining (admin endpoint).

        Args:
            reason: Trigger reason (typically 'manual')
            fields: List of fields to retrain

        Returns:
            Created RetrainingJob
        """
        try:
            job = RetrainingJob(
                id=uuid.uuid4(),
                trigger_reason=reason,
                fields=fields,
                status="pending",
                created_at=datetime.now(UTC),
                metadata={},
            )

            # Persist to database
            await self._persist_job(job)

            logger.info(
                "manual_retraining_triggered",
                job_id=job.id,
                fields=fields,
            )

            return job

        except Exception as e:
            logger.error("manual_retraining_trigger_failed", error=str(e))
            raise

    async def run_scheduled_retraining(self) -> RetrainingJob | None:
        """Run scheduled weekly retraining (Sunday at 2:00 AM).

        Skip condition: if a RetrainingJob with status='completed' exists in the last 7 days.

        Returns:
            Created RetrainingJob or None (if skipped)
        """
        try:
            # Check if completed job exists in last 7 days
            datetime.now(UTC) - timedelta(days=7)

            async with self.session_factory():
                # Query for completed jobs in last 7 days
                # Placeholder - would query retraining_jobs table
                recent_completed = False

                if recent_completed:
                    logger.info("scheduled_retraining_skipped_recent_job_exists")
                    return None

                # Create new scheduled job
                job = RetrainingJob(
                    id=uuid.uuid4(),
                    trigger_reason="scheduled",
                    fields=["sentiment_score", "risk_score", "discourse_act", "frame"],
                    status="pending",
                    created_at=datetime.now(UTC),
                    metadata={},
                )

                await self._persist_job(job)

                logger.info(
                    "scheduled_retraining_triggered",
                    job_id=job.id,
                )

                return job

        except Exception as e:
            logger.error("scheduled_retraining_failed", error=str(e))
            return None

    async def _persist_job(self, job: RetrainingJob) -> None:
        """Persist retraining job to database.

        Args:
            job: RetrainingJob to persist
        """
        try:
            # Insert into retraining_jobs table
            # For now, just log
            logger.info(
                "persist_retraining_job",
                job_id=job.id,
                trigger_reason=job.trigger_reason,
            )
        except Exception as e:
            logger.error("persist_retraining_job_failed", error=str(e))

    async def update_job_status(
        self, job_id: uuid.UUID, status: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Update retraining job status.

        Args:
            job_id: Job ID
            status: New status
            metadata: Optional metadata to update
        """
        try:
            async with self.session_factory():
                # Update retraining_jobs table
                # For now, just log
                logger.info(
                    "update_retraining_job_status",
                    job_id=job_id,
                    status=status,
                )

                if status in ("completed", "failed", "shadow_failed"):
                    # Update completed_at
                    pass

        except Exception as e:
            logger.error("update_job_status_failed", error=str(e))
