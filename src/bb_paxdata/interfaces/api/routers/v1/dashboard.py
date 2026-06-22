import pydantic
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend
from bb_paxdata.infrastructure.container.service_container import ServiceContainer
from bb_paxdata.interfaces.api.dependencies import (
    get_cache,
    get_current_reviewer,
    get_db,
)
from bb_paxdata.interfaces.api.schemas import (
    AnomalyTimelineItemResponse,
    CalibrationReportResponse,
    CalibrationTrendItem,
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


def get_dashboard_service(db: AsyncSession = Depends(get_db)):
    """Dependency injection for DashboardQueryService."""
    container = ServiceContainer.get_instance()
    return container.dashboard_query_service(db)


@router.get("/kpis", response_model=KpiStatsResponse)
async def get_kpi_stats(
    service=Depends(get_dashboard_service),
    cache: RedisCacheBackend = Depends(get_cache),
):
    """Retrieve global KPIs."""
    cache_key = "kpis"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    result = await service.get_kpi_stats()
    await cache.set(cache_key, result, ttl=60)
    return result


@router.get("/formulas/health", response_model=list[FormulaHealthResponse])
async def get_formula_health(
    service=Depends(get_dashboard_service),
    cache: RedisCacheBackend = Depends(get_cache),
):
    """Retrieve FP rates and correction rate metrics."""
    cache_key = "formulas_health"
    cached = await cache.get(cache_key)
    if cached:
        return cached
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
    service=Depends(get_dashboard_service),
    days: int = Query(default=30, ge=1, le=365, description="Lookback window in days"),
) -> list[FormulaTrendResponse]:
    """Retrieve historical daily false-positive rates per formula."""
    rows = await service.get_formula_health_trend(days=days)
    return [FormulaTrendResponse(**r) for r in rows]


@router.get("/trends", response_model=list[DailyTrendResponse])
async def get_daily_trends(service=Depends(get_dashboard_service)):
    """Daily PASS/FAIL counts for the trend line chart."""
    trends = await service.get_daily_trends()
    return [DailyTrendResponse(**t) for t in trends]


@router.get("/priorities", response_model=list[PriorityDistributionResponse])
async def get_priority_distribution(service=Depends(get_dashboard_service)):
    """HITL queue items by priority level."""
    dist = await service.get_priority_distribution()
    return [PriorityDistributionResponse(**d) for d in dist]


@router.get("/triggers", response_model=list[TriggerDistributionResponse])
async def get_trigger_distribution(service=Depends(get_dashboard_service)):
    """Queue items grouped by trigger reason."""
    dist = await service.get_trigger_distribution()
    return [TriggerDistributionResponse(**d) for d in dist]


@router.get("/consensus", response_model=list[ConsensusDistributionResponse])
async def get_consensus_distribution(service=Depends(get_dashboard_service)):
    """Anomaly classification statistics."""
    dist = await service.get_consensus_distribution()
    return [ConsensusDistributionResponse(**d) for d in dist]


@router.get("/bilateral/timeline")
async def get_bilateral_timeline(service=Depends(get_dashboard_service)):
    """Zaman kaydırıcısı için sıralanmış panel (file) listesi döner."""
    return await service.get_bilateral_timeline()


@router.get("/bilateral")
async def get_bilateral_sentiment(
    service=Depends(get_dashboard_service),
    file_id: str | None = Query(
        default=None,
        max_length=200,
        description="Panel/dosya filtresi — belirtilmezse tüm veriler aggregated döner.",
    ),
):
    """Bilateral sentiment matrix."""
    return await service.get_bilateral_sentiment(file_id=file_id)


@router.get("/anomalies", response_model=list[AnomalyTimelineItemResponse])
async def get_anomalies(
    service=Depends(get_dashboard_service),
    file_id: str | None = Query(
        None, max_length=200, description="Filter anomalies by panel/file_id"
    ),
    category: str | None = Query(
        None,
        max_length=100,
        description="Filter by fail_category (contradiction, hedging, risk etc.)",
    ),
    min_discrepancy: float = Query(
        0.0, ge=0.0, le=1.0, description="Filter by minimum discrepancy_score"
    ),
):
    """Retrieve chronologically ordered validation/contradiction anomalies."""
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
    service=Depends(get_dashboard_service),
    speaker_id: str | None = Query(None, description="Speaker ID / Name to analyze"),
):
    """Retrieve temporal drift analysis metrics for a given speaker (GARCH, Half-life, DKI)."""
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


@router.get("/calibration", response_model=CalibrationReportResponse)
async def get_calibration_report(
    db: AsyncSession = Depends(get_db),
) -> CalibrationReportResponse:
    """Retrieve the latest calibration report metrics."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from bb_paxdata.infrastructure.db.human_review_table import CalibrationReportORM

    stmt = (
        select(CalibrationReportORM)
        .order_by(CalibrationReportORM.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if not row:
        now_str = datetime.now(timezone.utc).isoformat()
        return CalibrationReportResponse(
            prompt_version="N/A",
            evaluation_period_start=now_str,
            evaluation_period_end=now_str,
            cohens_kappa_frame=None,
            cohens_kappa_risk=None,
            ai_human_f1_frame=None,
            ai_human_f1_risk=None,
            sbi_mae=None,
            total_reviews=0,
            total_disagreements=0,
            disagreement_rate=0.0,
            is_reliable=False,
            requires_prompt_update=False,
            requires_weight_update=False,
            alert_message="Sistemde henüz kalibrasyon verisi bulunmamaktadır.",
            top_disagreement_patterns=[],
        )

    disagreement_rate = (
        (row.total_disagreements / row.total_reviews * 100)
        if row.total_reviews > 0
        else 0.0
    )
    is_reliable = row.cohens_kappa_frame is not None and row.cohens_kappa_frame >= 0.67

    return CalibrationReportResponse(
        id=row.id,
        prompt_version=row.prompt_version,
        evaluation_period_start=(
            row.evaluation_period_start.isoformat()
            if row.evaluation_period_start
            else ""
        ),
        evaluation_period_end=(
            row.evaluation_period_end.isoformat() if row.evaluation_period_end else ""
        ),
        cohens_kappa_frame=row.cohens_kappa_frame,
        cohens_kappa_risk=row.cohens_kappa_risk,
        ai_human_f1_frame=row.ai_human_f1_frame,
        ai_human_f1_risk=row.ai_human_f1_risk,
        sbi_mae=row.sbi_mae,
        total_reviews=row.total_reviews,
        total_disagreements=row.total_disagreements,
        disagreement_rate=round(disagreement_rate, 2),
        is_reliable=is_reliable,
        requires_prompt_update=row.requires_prompt_update,
        requires_weight_update=row.requires_weight_update,
        alert_message=row.alert_message,
        top_disagreement_patterns=row.top_disagreement_patterns or [],
    )


@router.get("/calibration/trend", response_model=list[CalibrationTrendItem])
async def get_calibration_trend(
    months: int = Query(
        default=6, ge=1, le=12, description="Lookback window in months"
    ),
    db: AsyncSession = Depends(get_db),
) -> list[CalibrationTrendItem]:
    """Retrieve historical calibration trend metrics."""

    from sqlalchemy import select

    from bb_paxdata.infrastructure.db.human_review_table import CalibrationReportORM

    stmt = (
        select(CalibrationReportORM)
        .order_by(CalibrationReportORM.created_at.desc())
        .limit(months)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    TR_MONTHS = [
        "Oca",
        "Şub",
        "Mar",
        "Nis",
        "May",
        "Haz",
        "Tem",
        "Ağu",
        "Eyl",
        "Eki",
        "Kas",
        "Ara",
    ]

    if not rows:
        return []

    # Return rows ordered chronologically
    trend_items = []
    for row in reversed(rows):
        dt = row.created_at or row.evaluation_period_end
        month_name = TR_MONTHS[dt.month - 1] if dt else "Bilinmeyen"
        trend_items.append(
            CalibrationTrendItem(
                month=month_name,
                kappa=row.cohens_kappa_frame or 0.0,
                f1=row.ai_human_f1_frame or 0.0,
            )
        )
    return trend_items
