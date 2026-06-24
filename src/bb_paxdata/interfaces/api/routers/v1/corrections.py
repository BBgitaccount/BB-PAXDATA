"""Correction Store API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.correction_event import (
    CorrectionEvent,
)
from bb_paxdata.infrastructure.container.service_container import ServiceContainer
from bb_paxdata.infrastructure.db.repositories.correction_event_repository import (
    CorrectionEventRepository,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter(
    prefix="/corrections",
    tags=["Corrections"],
)


def get_correction_repository(db: AsyncSession = Depends(get_db)):
    """Dependency injection for CorrectionEventRepository."""
    return CorrectionEventRepository(db)


def get_correction_event_publisher():
    """Dependency injection for CorrectionEventPublisher."""
    container = ServiceContainer.get_instance()
    return container.correction_event_publisher()


class CorrectionEventCreateSchema(BaseModel):
    """Schema for creating a new correction event."""

    sentence_id: str = Field(..., description="ID of the sentence being corrected")
    field_corrected: str = Field(
        ..., description="Field being corrected (e.g., sentiment, frame, discourse_act)"
    )
    original_value: Any = Field(..., description="Original AI-generated value")
    corrected_value: Any = Field(..., description="Human-corrected value")
    prompt_version: str = Field(..., description="Prompt version used for analysis")
    ai_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="AI confidence score (0.0 to 1.0)"
    )
    corrector_id: str = Field(..., description="ID of the human corrector")
    context_snapshot: dict[str, Any] | None = Field(
        None, description="Pipeline state at time of correction"
    )


class CorrectionEventResponseSchema(BaseModel):
    """Schema for correction event response."""

    id: str
    sentence_id: str
    field_corrected: str
    original_value: Any
    corrected_value: Any
    prompt_version: str
    ai_confidence: float
    corrector_id: str
    timestamp: datetime
    context_snapshot: dict[str, Any] | None = None

    class Config:
        from_attributes = True


class CorrectionStatsResponseSchema(BaseModel):
    """Schema for correction statistics response."""

    total_corrections: int
    by_field: dict[str, int]
    by_prompt_version: dict[str, int]
    high_confidence_errors: int
    average_confidence: float
    correction_rate: float


@router.post("", response_model=CorrectionEventResponseSchema, status_code=201)
async def create_correction(
    correction: CorrectionEventCreateSchema,
    repo=Depends(get_correction_repository),
    publisher=Depends(get_correction_event_publisher),
):
    """
    Create a new correction event.

    Records a human correction to AI-generated analysis for learning purposes.
    This is append-only - corrections cannot be modified or deleted after creation.
    """
    event = CorrectionEvent(
        id=str(uuid.uuid4()),
        sentence_id=correction.sentence_id,
        field_corrected=correction.field_corrected,
        original_value=correction.original_value,
        corrected_value=correction.corrected_value,
        prompt_version=correction.prompt_version,
        ai_confidence=correction.ai_confidence,
        corrector_id=correction.corrector_id,
        timestamp=datetime.utcnow(),
        context_snapshot=correction.context_snapshot,
    )

    saved_event = await repo.save(event)

    # Publish event to event bus for Pattern Miner
    await publisher.publish_correction_created(saved_event)

    return CorrectionEventResponseSchema.model_validate(saved_event)


@router.get("", response_model=list[CorrectionEventResponseSchema])
async def list_corrections(
    field_corrected: Annotated[str | None, Query()] = None,
    prompt_version: Annotated[str | None, Query()] = None,
    corrector_id: Annotated[str | None, Query()] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    repo=Depends(get_correction_repository),
):
    """
    List correction events with optional filters.

    Query parameters:
    - field_corrected: Filter by field being corrected
    - prompt_version: Filter by prompt version
    - corrector_id: Filter by corrector ID
    - start_date: Filter by start date
    - end_date: Filter by end date
    - limit: Maximum number of results (default: 100, max: 1000)
    - offset: Pagination offset (default: 0)
    """
    events = await repo.list(
        field_corrected=field_corrected,
        prompt_version=prompt_version,
        corrector_id=corrector_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return [CorrectionEventResponseSchema.model_validate(event) for event in events]


@router.get("/{event_id}", response_model=CorrectionEventResponseSchema)
async def get_correction(
    event_id: str,
    repo=Depends(get_correction_repository),
):
    """Retrieve a single correction event by ID."""
    event = await repo.get_by_id(event_id)

    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Correction event not found: {event_id}",
        )

    return CorrectionEventResponseSchema.model_validate(event)


@router.get(
    "/sentence/{sentence_id}", response_model=list[CorrectionEventResponseSchema]
)
async def get_corrections_by_sentence(
    sentence_id: str,
    repo=Depends(get_correction_repository),
):
    """Retrieve all correction events for a specific sentence."""
    events = await repo.get_by_sentence_id(sentence_id)
    return [CorrectionEventResponseSchema.model_validate(event) for event in events]


@router.get("/stats/summary", response_model=CorrectionStatsResponseSchema)
async def get_correction_stats(
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    repo=Depends(get_correction_repository),
):
    """
    Get correction statistics.

    Query parameters:
    - start_date: Optional start date for statistics range
    - end_date: Optional end date for statistics range

    Returns:
    - Total corrections
    - Breakdown by field
    - Breakdown by prompt version
    - High-confidence error count
    - Average confidence
    - Correction rate
    """
    stats = await repo.get_stats(start_date=start_date, end_date=end_date)
    return CorrectionStatsResponseSchema.model_validate(stats)


@router.get("/stats/field/{field}")
async def get_field_distribution(
    field: str,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    repo=Depends(get_correction_repository),
):
    """
    Get correction delta distribution for a specific field.

    Returns statistics about how values are being corrected for this field.
    """
    distribution = await repo.get_field_distribution(
        field=field, start_date=start_date, end_date=end_date
    )
    return distribution


@router.get("/stats/compare-versions")
async def compare_prompt_versions(
    version1: Annotated[str, Query(..., description="First prompt version to compare")],
    version2: Annotated[
        str, Query(..., description="Second prompt version to compare")
    ],
    repo=Depends(get_correction_repository),
):
    """
    Compare correction rates between two prompt versions.

    Returns statistics comparing the error rates and patterns between versions.
    """
    comparison = await repo.get_prompt_version_comparison(version1, version2)
    return comparison
