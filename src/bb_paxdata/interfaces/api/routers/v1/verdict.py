from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend
from bb_paxdata.infrastructure.db.repositories.formula_validation import (
    FormulaValidationRepository,
)
from bb_paxdata.infrastructure.messaging.publisher import (
    RedisEventPublisher,
    get_publisher,
)
from bb_paxdata.interfaces.api.dependencies import PermissionChecker, get_cache, get_db
from bb_paxdata.interfaces.api.schemas import (
    AuditEntryResponse,
    VerdictPayload,
    VerdictResponse,
)

router = APIRouter(prefix="/verdict", tags=["Verdict"])


@router.get("/audit", response_model=list[AuditEntryResponse])
async def get_audit_trail(
    limit: int = Query(20),
    db: AsyncSession = Depends(get_db),
    # Require at least 'view' permission to view audit trail
    _has_permission: bool = Depends(PermissionChecker("view")),
):
    """Retrieve recent reviewer actions and decision logs."""
    repo = FormulaValidationRepository(db)
    return await repo.get_audit_trail(limit=limit)


@router.post("", response_model=VerdictResponse)
async def submit_verdict(
    payload: VerdictPayload,
    db: AsyncSession = Depends(get_db),
    cache: RedisCacheBackend = Depends(get_cache),
    publisher: RedisEventPublisher = Depends(get_publisher),
    # Require at least 'verdict' level permission to submit review responses
    _has_permission: bool = Depends(PermissionChecker("verdict")),
):
    """Submit a reviewer decision (CONFIRMED_PASS, CONFIRMED_FAIL, or CORRECTED value) atomically."""
    repo = FormulaValidationRepository(db)
    try:
        result = await repo.submit_verdict_atomic(
            log_id=payload.log_id,
            verdict=payload.verdict,
            corrected_value=payload.corrected_value,
            note=payload.note,
            confidence=payload.confidence,
            justification=payload.justification,
            reviewer_id=payload.reviewer_id,
        )

        from bb_paxdata.infrastructure.events.publisher import WORMEventPublisher

        await WORMEventPublisher(db).emit(
            aggregate_type="HumanReview",
            aggregate_id=str(payload.log_id),
            event_type="VerdictSubmitted",
            payload={
                "verdict": payload.verdict,
                "corrected_value": payload.corrected_value,
                "note": payload.note,
                "confidence": payload.confidence,
                "justification": payload.justification,
            },
            actor_id=payload.reviewer_id,
        )

        await db.commit()

        # Evict stale cache values so the dashboard displays fresh metrics
        await cache.delete("kpis")
        await cache.delete("formulas_health")

        # Broadcast the change to all connected WebSocket clients
        from bb_paxdata.interfaces.api.routers.ws.queue_ws import manager as ws_manager

        await ws_manager.broadcast(
            {
                "event": "queue_updated",
                "log_id": payload.log_id,
                "verdict": payload.verdict,
                "reviewer_id": payload.reviewer_id,
            }
        )

        # Publish verdict event to Redis channel
        await publisher.publish_event(
            "verdict_events", "verdict_submitted", payload.model_dump()
        )

        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
