from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.models import Sentence
from bb_paxdata.infrastructure.db.repositories.formula_validation import (
    FormulaValidationRepository,
)
from bb_paxdata.interfaces.api.dependencies import get_db
from bb_paxdata.interfaces.api.schemas import (
    FailQueueItemResponse,
    PanelContext,
    SimilarCaseResponse,
    SpeakerContext,
    TripletContextResponse,
)

router = APIRouter(prefix="/queue", tags=["Queue"])


@router.get("", response_model=list[FailQueueItemResponse])
async def get_fail_queue(
    formula_name: Optional[str] = Query(None),
    status_filter: str = Query("unreviewed"),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve failed validation logs with sentence details and AI scores, ordered by priority score."""
    repo = FormulaValidationRepository(db)
    # Map frontend 'Tümü' filter to None
    f_name = None if formula_name == "Tümü" else formula_name
    return await repo.get_fail_queue_with_context(
        formula_name=f_name, status_filter=status_filter, limit=limit
    )


@router.get("/context/{sent_id}", response_model=TripletContextResponse)
async def get_triplet_context(sent_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve the target sentence, its previous and next sentence, and speaker/panel metadata."""
    repo = FormulaValidationRepository(db)
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
    country: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve similar historical failures for the same validation formula to guide the reviewer."""
    repo = FormulaValidationRepository(db)
    return await repo.get_similar_cases(
        sent_id=sent_id, formula_name=formula_name, country=country
    )
