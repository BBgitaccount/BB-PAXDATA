"""Celery application configuration."""

from bb_paxdata.config.settings import Settings, get_settings
from celery import Celery

_settings: Settings | None = None


def _get_settings() -> Settings:
    """Get settings with lazy initialization."""
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """
    Factory function to create Celery app with dependency injection.
    """
    if settings is None:
        settings = _get_settings()

    app = Celery(
        "paxdata",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=[
            "bb_paxdata.infrastructure.tasks.analysis_tasks",
            "bb_paxdata.infrastructure.tasks.graph_tasks",
            "bb_paxdata.infrastructure.webhooks.tasks",
            "bb_paxdata.infrastructure.export.tasks",
            "bb_paxdata.infrastructure.tasks.consensus_tasks",  # CORRECTED (E05-M-05)
        ],
    )

    # Queue routing by community affinity
    # RATIONALE: Community 1 (Fischer DNA) and Community 8 (AnalysisPipeline)
    # have conflicting resource needs (CPU vs I/O). Separate queues.
    app.conf.task_routes = {
        "bb_paxdata.infrastructure.tasks.analysis_tasks.analyze_sentence": {
            "queue": "ai_cpu"
        },
        "bb_paxdata.infrastructure.tasks.analysis_tasks.analyze_segment": {
            "queue": "ai_cpu"
        },
        "bb_paxdata.infrastructure.tasks.graph_tasks.reindex_communities": {
            "queue": "graph_io"
        },
        "bb_paxdata.infrastructure.tasks.graph_tasks.export_graph_snapshot": {
            "queue": "graph_io"
        },
        "webhooks.process_outbox_queue": {"queue": "graph_io"},
        "webhooks.dispatch": {"queue": "graph_io"},
    }

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,  # Re-queue on worker crash
        worker_prefetch_multiplier=1,  # Fair dispatch, one task at a time per worker
        task_track_started=True,
        task_soft_time_limit=300,  # 5 min soft limit → raises SoftTimeLimitExceeded
        task_time_limit=600,  # 10 min hard kill
        broker_connection_retry_on_startup=True,
        result_expires=3600,  # 1h TTL on results
        worker_send_task_events=True,
        task_send_sent_event=True,
    )

    # Celery Beat schedule for scheduled tasks
    app.conf.beat_schedule = {
        "nightly-quality-regression": {
            "task": "bb_paxdata.infrastructure.tasks.analysis_tasks.run_quality_regression",
            "schedule": 86400,  # every 24 hours
        },
        "nightly-parquet-export": {
            "task": "bb_paxdata.infrastructure.tasks.analysis_tasks.export_data_lake",
            "schedule": 86400,  # every 24 hours (nightly)
            "args": ["paxdata-archive"],
        },
        "process-outbox-events": {
            "task": "webhooks.process_outbox_queue",
            "schedule": 10.0,  # every 10 seconds
        },
    }

    return app


# Default app for backward compatibility (lazy initialization)
app: Celery | None = None


def get_celery_app() -> Celery:
    """Get or create the default Celery app."""
    global app
    if app is None:
        app = create_celery_app()
    return app
