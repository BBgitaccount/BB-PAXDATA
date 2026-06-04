"""Celery tasks for sentence analysis and quality regression."""

import asyncio
import logging
import subprocess
import sys
from typing import Any

from bb_paxdata.infrastructure.tasks.celery_app import app

logger = logging.getLogger(__name__)


@app.task(
    name="bb_paxdata.infrastructure.tasks.analysis_tasks.analyze_sentence",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(TimeoutError, ConnectionError),
    queue="ai_cpu",
)
def analyze_sentence_task(
    self, sent_id: str, text: str, context: dict[str, Any]
) -> dict[str, Any]:
    """Analyze a single sentence asynchronously.

    INVARIANT: Must use asyncio.run() with a FRESH event loop.
    INVARIANT: Must use SessionLocalCLI (NullPool) to avoid connection sharing across forks.
    INVARIANT: Must emit DomainEvent via EventPublisher after success.
    """
    from bb_paxdata.application.services.analysis_service import run_sentence_analysis
    from bb_paxdata.infrastructure.db.session import SessionLocalCLI
    from bb_paxdata.infrastructure.events.publisher import EventPublisher

    async def _run():
        async with SessionLocalCLI() as db:
            publisher = EventPublisher(db)
            result = await run_sentence_analysis(sent_id, text, context)
            await publisher.emit(
                aggregate_type="AISentenceAnalysis",
                aggregate_id=sent_id,
                event_type="AnalysisCompleted",
                payload=result,
                actor_id="system",
                correlation_id=self.request.id,
            )
            await db.commit()
            return result

    return asyncio.run(_run())


@app.task(
    name="bb_paxdata.infrastructure.tasks.analysis_tasks.run_quality_regression",
    queue="ai_cpu",
)
def run_quality_regression() -> dict[str, Any]:
    """Scheduled task: run golden dataset regression and alert on failure."""
    result = subprocess.run(
        [sys.executable, "scripts/run_quality_pipeline.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:],  # Last 2000 chars
        "stderr": result.stderr[-500:],
    }


@app.task(
    name="bb_paxdata.infrastructure.tasks.analysis_tasks.export_data_lake",
    queue="graph_io",
)
def export_data_lake_task(s3_bucket: str) -> dict[str, Any]:
    """Scheduled task: export data lake to Parquet (Task 4.5)."""
    from bb_paxdata.config.settings import get_settings
    from bb_paxdata.infrastructure.db.session import SessionLocalCLI
    from bb_paxdata.infrastructure.lake.parquet_exporter import export_to_parquet

    settings = get_settings()
    # If endpoint_url is configured, e.g. MinIO in development
    minio_url = "http://localhost:9000" if "localhost" in settings.redis_url else None

    async def _run():
        async with SessionLocalCLI() as db:
            sentences_key = await export_to_parquet(
                db=db,
                s3_bucket=s3_bucket,
                aws_endpoint_url=minio_url,
            )
            return {"sentences_key": sentences_key}

    return asyncio.run(_run())
