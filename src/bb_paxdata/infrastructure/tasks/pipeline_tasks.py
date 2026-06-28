"""Celery tasks for executing the end-to-end data pipeline."""

import subprocess
import time

import structlog

from bb_paxdata.infrastructure.tasks.celery_app import get_celery_app

logger = structlog.get_logger(__name__)
app = get_celery_app()


@app.task(
    name="bb_paxdata.infrastructure.tasks.pipeline_tasks.run_full_pipeline_task",
    bind=True,
    soft_time_limit=3600,  # 1 hour soft limit for full pipeline
    time_limit=3660,  # 1 hour + 1 min hard limit
)
def run_full_pipeline_task(self) -> dict:
    """
    Executes the main pipeline script (run_pipeline.py) as a background task.
    This task will block the celery worker until the pipeline is complete.
    Real-time progress is broadcasted via Redis by the build commands themselves.
    """
    logger.info("Starting full pipeline task execution")
    start_time = time.time()

    try:
        # Run the pipeline script. The worker's current working directory is /app.
        result = subprocess.run(
            ["poetry", "run", "python", "run_pipeline.py"],
            capture_output=True,
            text=True,
            check=False,
        )

        duration = time.time() - start_time

        if result.returncode == 0:
            logger.info("Pipeline task completed successfully", duration=duration)
            return {
                "status": "success",
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        else:
            logger.error(
                "Pipeline task failed",
                returncode=result.returncode,
                stderr=result.stderr,
            )
            return {
                "status": "failed",
                "returncode": result.returncode,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

    except Exception as e:
        duration = time.time() - start_time
        logger.exception("Exception occurred while running pipeline task")
        return {"status": "error", "error": str(e), "duration": duration}
