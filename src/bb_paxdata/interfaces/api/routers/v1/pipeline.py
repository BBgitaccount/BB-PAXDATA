"""Router for triggering the data pipeline execution."""

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from bb_paxdata.infrastructure.tasks.pipeline_tasks import run_full_pipeline_task

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["pipeline"])


class PipelineStartResponse(BaseModel):
    """Response model for starting the pipeline."""

    task_id: str
    message: str


@router.post(
    "/pipeline/start",
    response_model=PipelineStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Full Pipeline",
    description="Triggers the execution of the full data pipeline as a background Celery task.",
)
async def start_pipeline():
    """
    Start the pipeline execution asynchronously.
    """
    try:
        # Submit task to Celery
        task = run_full_pipeline_task.delay()
        logger.info("Pipeline task submitted successfully", task_id=task.id)

        return PipelineStartResponse(
            task_id=task.id,
            message="Pipeline execution started successfully. Check dashboard for progress.",
        )
    except Exception as e:
        logger.exception("Failed to start pipeline task")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start pipeline: {e!s}",
        )
