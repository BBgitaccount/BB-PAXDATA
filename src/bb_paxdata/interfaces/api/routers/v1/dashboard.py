import pydantic
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.services.dashboard_query import DashboardQueryService
from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend
from bb_paxdata.interfaces.api.dependencies import (
    get_cache,
    get_current_reviewer,
    get_db,
)
from bb_paxdata.interfaces.api.schemas import (
    AnomalyTimelineItemResponse,
    ConsensusDistributionResponse,
    DailyTrendResponse,
    DkiHistoryItemResponse,
    DriftEventItemResponse,
    FormulaHealthResponse,
    GarchResultResponse,
    HalfLifeResultResponse,
    KpiStatsResponse,
    PriorityDistributionResponse,
    TemporalDriftResponse,
    TriggerDistributionResponse,
)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_reviewer)],
)


@router.get("/kpis", response_model=KpiStatsResponse)
async def get_kpi_stats(
    db: AsyncSession = Depends(get_db),
    cache: RedisCacheBackend = Depends(get_cache),
):
    """Retrieve global KPIs."""
    cache_key = "kpis"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    service = DashboardQueryService(db)
    result = await service.get_kpi_stats()
    await cache.set(cache_key, result, ttl=60)
    return result


@router.get("/formulas/health", response_model=list[FormulaHealthResponse])
async def get_formula_health(
    db: AsyncSession = Depends(get_db),
    cache: RedisCacheBackend = Depends(get_cache),
):
    """Retrieve FP rates and correction rate metrics."""
    cache_key = "formulas_health"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    service = DashboardQueryService(db)
    result = await service.get_formula_health()
    await cache.set(cache_key, result, ttl=60)
    return result


class FormulaTrendResponse(pydantic.BaseModel):
    """Daily false-positive rate per formula for trend charting."""

    date: str
    formula_name: str
    fail_count: int
    false_positive_count: int
    false_positive_rate: float


@router.get("/formulas/health/trend", response_model=list[FormulaTrendResponse])
async def get_formula_health_trend(
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365, description="Lookback window in days"),
) -> list[FormulaTrendResponse]:
    """Retrieve historical daily false-positive rates per formula."""
    service = DashboardQueryService(db)
    rows = await service.get_formula_health_trend(days=days)
    return [FormulaTrendResponse(**r) for r in rows]


@router.get("/trends", response_model=list[DailyTrendResponse])
async def get_daily_trends(db: AsyncSession = Depends(get_db)):
    """Daily PASS/FAIL counts for the trend line chart."""
    service = DashboardQueryService(db)
    trends = await service.get_daily_trends()
    return [DailyTrendResponse(**t) for t in trends]


@router.get("/priorities", response_model=list[PriorityDistributionResponse])
async def get_priority_distribution(db: AsyncSession = Depends(get_db)):
    """HITL queue items by priority level."""
    service = DashboardQueryService(db)
    dist = await service.get_priority_distribution()
    return [PriorityDistributionResponse(**d) for d in dist]


@router.get("/triggers", response_model=list[TriggerDistributionResponse])
async def get_trigger_distribution(db: AsyncSession = Depends(get_db)):
    """Queue items grouped by trigger reason."""
    service = DashboardQueryService(db)
    dist = await service.get_trigger_distribution()
    return [TriggerDistributionResponse(**d) for d in dist]


@router.get("/consensus", response_model=list[ConsensusDistributionResponse])
async def get_consensus_distribution(db: AsyncSession = Depends(get_db)):
    """Anomaly classification statistics."""
    service = DashboardQueryService(db)
    dist = await service.get_consensus_distribution()
    return [ConsensusDistributionResponse(**d) for d in dist]


@router.get("/bilateral/timeline")
async def get_bilateral_timeline(db: AsyncSession = Depends(get_db)):
    """Zaman kaydırıcısı için sıralanmış panel (file) listesi döner."""
    service = DashboardQueryService(db)
    return await service.get_bilateral_timeline()


@router.get("/bilateral")
async def get_bilateral_sentiment(
    db: AsyncSession = Depends(get_db),
    file_id: str | None = Query(
        default=None,
        description="Panel/dosya filtresi — belirtilmezse tüm veriler aggregated döner.",
    ),
):
    """Bilateral sentiment matrix."""
    service = DashboardQueryService(db)
    return await service.get_bilateral_sentiment(file_id=file_id)


@router.get("/anomalies", response_model=list[AnomalyTimelineItemResponse])
async def get_anomalies(
    db: AsyncSession = Depends(get_db),
    file_id: str | None = Query(None, description="Filter anomalies by panel/file_id"),
    category: str | None = Query(
        None, description="Filter by fail_category (contradiction, hedging, risk etc.)"
    ),
    min_discrepancy: float = Query(
        0.0, description="Filter by minimum discrepancy_score"
    ),
):
    """Retrieve chronologically ordered validation/contradiction anomalies."""
    service = DashboardQueryService(db)
    failures = await service.get_anomalies(
        file_id=file_id, category=category, min_discrepancy=min_discrepancy
    )

    return [
        AnomalyTimelineItemResponse(
            fail_id=f.fail_id,
            sent_id=f.sent_id,
            file_id=f.file_id,
            speaker_name=f.speaker_name,
            country=f.country,
            check_type=f.check_type,
            formula_value=f.formula_value,
            ai_value=f.ai_value,
            discrepancy_score=f.discrepancy_score,
            original_sentence=f.original_sentence,
            fail_reason=f.fail_reason,
            fail_category=f.fail_category,
            anomaly_types=f.anomaly_types,
            processed_at=f.processed_at.isoformat() if f.processed_at else None,
            negation_type=f.negation_type,
            negation_scope=f.negation_scope,
            linguistic_marker=f.linguistic_marker,
            contextual_factor=f.contextual_factor,
            temporal_factor=f.temporal_factor,
        )
        for f in failures
    ]


@router.get("/drift", response_model=TemporalDriftResponse)
async def get_temporal_drift(
    speaker_id: str | None = Query(None, description="Speaker ID / Name to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve temporal drift analysis metrics for a given speaker (GARCH, Half-life, DKI)."""
    service = DashboardQueryService(db)
    res = await service.get_temporal_drift(speaker_id=speaker_id)

    return TemporalDriftResponse(
        selected_speaker=res["selected_speaker"],
        garch=GarchResultResponse(
            sentiment_volatility=res["garch"]["sentiment_volatility"],
            volatility_regime=res["garch"]["volatility_regime"],
            volatilities_series=res["garch"]["volatilities_series"],
            sentiment_series=res["garch"]["sentiment_series"],
        ),
        half_life=HalfLifeResultResponse(
            salience_half_life=res["half_life"]["salience_half_life"],
            decay_rate=res["half_life"]["decay_rate"],
            agenda_permanence=res["half_life"]["agenda_permanence"],
            counts_series=res["half_life"]["counts_series"],
        ),
        dki=[DkiHistoryItemResponse(**d) for d in res["dki"]],
        drift_events=[DriftEventItemResponse(**d) for d in res["drift_events"]],
        speakers=res["speakers"],
    )
