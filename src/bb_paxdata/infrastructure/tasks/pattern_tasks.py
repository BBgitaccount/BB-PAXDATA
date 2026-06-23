"""Celery tasks for pattern analysis of correction events."""

from __future__ import annotations

from typing import Any

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.services.pattern_analyzer import PatternAnalyzer
from bb_paxdata.infrastructure.db.repositories.correction_event_repository import (
    CorrectionEventRepository,
)
from bb_paxdata.infrastructure.tasks.celery_app import get_celery_app

celery_app = get_celery_app()


class PatternAnalysisTask(Task):
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
    base=PatternAnalysisTask,
    name="bb_paxdata.infrastructure.tasks.pattern_tasks.run_pattern_analysis",
    bind=True,
)
def run_pattern_analysis(
    self,
    limit: int = 1000,
) -> dict:
    """
    Async task to run pattern analysis on recent correction events.

    This task analyzes the most recent N correction events to detect:
    - Systematic error patterns
    - Threshold anomalies
    - Prompt version regressions
    - Field-based correction distributions

    Args:
        limit: Number of recent events to analyze (default: 1000)

    Returns:
        Dict with analysis results and detected patterns
    """
    import asyncio

    async def _analyze() -> dict:
        repo = CorrectionEventRepository(self.db)
        analyzer = PatternAnalyzer(repository=repo)

        report = await analyzer.analyze_recent_events(limit=limit)

        # Publish report via event bus for WebSocket notification
        from bb_paxdata.infrastructure.container.service_container import (
            ServiceContainer,
        )

        container = ServiceContainer.get_instance()
        await container.event_bus.publish(
            channel="pattern_reports",
            event_type="PatternAnalysisCompleted",
            payload=report.to_dict(),
        )

        return report.to_dict()

    return asyncio.run(_analyze())


@celery_app.task(
    base=PatternAnalysisTask,
    name="bb_paxdata.infrastructure.tasks.pattern_tasks.run_threshold_triggered_analysis",
    bind=True,
)
def run_threshold_triggered_analysis(
    self,
    threshold_count: int = 50,
) -> dict:
    """
    Async task to run pattern analysis when threshold is reached.

    This task is triggered when N new correction events are accumulated.
    Useful for more frequent analysis when correction volume is high.

    Args:
        threshold_count: Minimum number of events to trigger analysis

    Returns:
        Dict with analysis results and detected patterns
    """
    import asyncio

    async def _analyze() -> dict:
        repo = CorrectionEventRepository(self.db)
        analyzer = PatternAnalyzer(repository=repo)

        # Get recent events up to threshold
        events = await repo.get_recent(limit=threshold_count)

        if len(events) < threshold_count:
            return {
                "status": "skipped",
                "reason": f"Insufficient events: {len(events)} < {threshold_count}",
            }

        report = await analyzer.analyze_recent_events(limit=threshold_count)

        # Publish report via event bus
        from bb_paxdata.infrastructure.container.service_container import (
            ServiceContainer,
        )

        container = ServiceContainer.get_instance()
        await container.event_bus.publish(
            channel="pattern_reports",
            event_type="ThresholdPatternAnalysisCompleted",
            payload=report.to_dict(),
        )

        return report.to_dict()

    return asyncio.run(_analyze())
