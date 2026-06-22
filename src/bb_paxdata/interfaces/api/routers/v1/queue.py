from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.container.service_container import ServiceContainer
from bb_paxdata.infrastructure.db.models import FormulaValidationLog, Sentence
from bb_paxdata.interfaces.api.dependencies import get_db
from bb_paxdata.interfaces.api.schemas import (
    FailQueueItemResponse,
    PanelContext,
    SimilarCaseResponse,
    SpeakerContext,
    TripletContextResponse,
)

router = APIRouter(prefix="/queue", tags=["Queue"])


def get_formula_validation_repository(db: AsyncSession = Depends(get_db)):
    """Dependency injection for FormulaValidationRepository."""
    container = ServiceContainer.get_instance()
    return container.formula_validation_repository(db)


@router.get("", response_model=list[FailQueueItemResponse])
async def get_fail_queue(
    repo=Depends(get_formula_validation_repository),
    formula_name: str | None = Query(None, max_length=200),
    status_filter: str = Query("unreviewed", pattern="^(unreviewed|all|reviewed)$"),
    limit: int = Query(50, ge=1, le=500),
):
    """Retrieve failed validation logs with sentence details and AI scores, ordered by priority score."""
    # Map frontend 'Tümü' filter to None
    f_name = None if formula_name == "Tümü" else formula_name
    return await repo.get_fail_queue_with_context(
        formula_name=f_name, status_filter=status_filter, limit=limit
    )


@router.get("/context/{sent_id}", response_model=TripletContextResponse)
async def get_triplet_context(
    sent_id: str,
    db: AsyncSession = Depends(get_db),
    repo=Depends(get_formula_validation_repository),
):
    """Retrieve the target sentence, its previous and next sentence, and speaker/panel metadata."""
    context_data = await repo.get_triplet_context(sent_id)

    # Query database to enrich speaker and panel context from the target sentence
    stmt = select(Sentence).where(Sentence.sent_id == sent_id)
    result = await db.execute(stmt)
    sentence = result.scalar_one_or_none()

    speaker = None
    panel = None
    if sentence:
        speaker = SpeakerContext(
            name=sentence.speaker_name or "Unknown",
            country=sentence.country or "Unknown",
            role="Diplomatic Speaker",
            power_level=sentence.power_level or 0,
            influence_tier="High" if (sentence.power_level or 0) >= 7 else "Medium",
            bloc="N/A",
        )
        panel = PanelContext(
            file_id=sentence.file_id or "Unknown",
            panel_number=1,
            theme="Diplomatic Dialogue Analysis",
        )

    return TripletContextResponse(
        prev=context_data.get("prev"),
        current=context_data.get("current") or (sentence.text if sentence else None),
        next=context_data.get("next"),
        speaker=speaker,
        panel=panel,
    )


@router.get(
    "/similar/{sent_id}/{formula_name}", response_model=list[SimilarCaseResponse]
)
async def get_similar_cases(
    sent_id: str,
    formula_name: str,
    country: str | None = Query(None),
    repo=Depends(get_formula_validation_repository),
):
    """Retrieve similar historical failures for the same validation formula to guide the reviewer."""
    return await repo.get_similar_cases(
        sent_id=sent_id, formula_name=formula_name, country=country
    )


@router.get("/context/by-log-id/{log_id}", response_model=TripletContextResponse)
async def get_triplet_context_by_log_id(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    repo=Depends(get_formula_validation_repository),
):
    """Retrieve triplet context by log_id (resolves sent_id internally)."""

    # First, get the sent_id from the log
    stmt = select(FormulaValidationLog).where(
        FormulaValidationLog.log_id == log_id,
        FormulaValidationLog.is_current,
    )
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        raise ValueError(f"Log {log_id} not found")

    if log.entity_type != "sentence":
        raise ValueError(f"Log {log_id} is not a sentence entity")

    sent_id = log.entity_id

    # Now get the context using sent_id
    context_data = await repo.get_triplet_context(sent_id)

    # Query database to enrich speaker and panel context from the target sentence
    stmt = select(Sentence).where(Sentence.sent_id == sent_id)
    result = await db.execute(stmt)
    sentence = result.scalar_one_or_none()

    speaker = None
    panel = None
    if sentence:
        speaker = SpeakerContext(
            name=sentence.speaker_name or "Unknown",
            country=sentence.country or "Unknown",
            role="Diplomatic Speaker",
            power_level=sentence.power_level or 0,
            influence_tier="High" if (sentence.power_level or 0) >= 7 else "Medium",
            bloc="N/A",
        )
        panel = PanelContext(
            file_id=sentence.file_id or "Unknown",
            panel_number=1,
            theme="Diplomatic Dialogue Analysis",
        )

    return TripletContextResponse(
        prev=context_data.get("prev"),
        current=context_data.get("current") or (sentence.text if sentence else None),
        next=context_data.get("next"),
        speaker=speaker,
        panel=panel,
    )


@router.get("/similar/by-log-id/{log_id}", response_model=list[SimilarCaseResponse])
async def get_similar_cases_by_log_id(
    log_id: int,
    country: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    repo=Depends(get_formula_validation_repository),
):
    """Retrieve similar cases by log_id (resolves sent_id and formula_name internally)."""

    # First, get the sent_id and formula_name from the log
    stmt = select(FormulaValidationLog).where(
        FormulaValidationLog.log_id == log_id,
        FormulaValidationLog.is_current,
    )
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        raise ValueError(f"Log {log_id} not found")

    if log.entity_type != "sentence":
        raise ValueError(f"Log {log_id} is not a sentence entity")

    sent_id = log.entity_id
    formula_name = log.formula_name

    # Now get similar cases using sent_id and formula_name
    return await repo.get_similar_cases(
        sent_id=sent_id, formula_name=formula_name, country=country
    )


@router.get("/log/{log_id}", response_model=FailQueueItemResponse)
async def get_queue_item_by_log_id(
    log_id: int,
    repo=Depends(get_formula_validation_repository),
):
    """Fallback: Retrieve queue item by log_id (returns sent_id and formula_name)."""

    # Get the queue item with context
    queue_items = await repo.get_fail_queue_with_context(
        formula_name=None, status_filter="all", limit=1
    )

    # Find the specific log_id
    for item in queue_items:
        if item.log_id == log_id:
            return item

    raise ValueError(f"Log {log_id} not found in queue")
