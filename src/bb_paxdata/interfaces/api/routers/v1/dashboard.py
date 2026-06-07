from typing import Any, Optional

import pydantic
from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.services.drift_algorithms import (
    calculate_entity_salience_half_life,
    estimate_sentiment_garch_volatility,
)
from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend
from bb_paxdata.infrastructure.db.country_models import BilateralSentimentTable
from bb_paxdata.infrastructure.db.dki_table import DKIResultModel
from bb_paxdata.infrastructure.db.drift_events import DriftEvent
from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
from bb_paxdata.infrastructure.db.models import (
    AIFailAnalysis,
    AISentenceAnalysis,
    File,
    FormulaValidationLog,
    Sentence,
)
from bb_paxdata.infrastructure.db.repositories.formula_validation import (
    FormulaValidationRepository,
)
from bb_paxdata.interfaces.api.dependencies import get_cache, get_db
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

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _normalize_count(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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
    repo = FormulaValidationRepository(db)
    result = await repo.get_kpi_stats()
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
    repo = FormulaValidationRepository(db)
    result = await repo.get_formula_health()
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
    """Retrieve historical daily false-positive rates per formula.

    A rising FP rate signals a formula threshold needs recalibration.
    Only considers rows where status='FAIL'; treats human_verdict='CONFIRMED_PASS'
    as a false positive (i.e. the formula incorrectly flagged a valid sentence).
    """
    import datetime

    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

    stmt = (
        select(
            func.date(FormulaValidationLog.created_at).label("day"),
            FormulaValidationLog.formula_name,
            func.count(FormulaValidationLog.log_id).label("total_fail"),
            func.sum(
                case(
                    (FormulaValidationLog.human_verdict == "CONFIRMED_PASS", 1),
                    else_=0,
                )
            ).label("fp_count"),
        )
        .where(
            FormulaValidationLog.status == "FAIL",
            FormulaValidationLog.created_at >= since,
        )
        .group_by(
            func.date(FormulaValidationLog.created_at),
            FormulaValidationLog.formula_name,
        )
        .order_by(func.date(FormulaValidationLog.created_at).asc())
    )

    res = await db.execute(stmt)
    rows = res.all()

    return [
        FormulaTrendResponse(
            date=str(r.day),
            formula_name=r.formula_name,
            fail_count=int(r.total_fail),
            false_positive_count=int(r.fp_count or 0),
            false_positive_rate=(
                round(int(r.fp_count or 0) / int(r.total_fail), 4)
                if int(r.total_fail) > 0
                else 0.0
            ),
        )
        for r in rows
    ]


@router.get("/trends", response_model=list[DailyTrendResponse])
async def get_daily_trends(db: AsyncSession = Depends(get_db)):
    """Daily PASS/FAIL counts for the trend line chart."""
    stmt = (
        select(
            func.date(FormulaValidationLog.created_at).label("day"),
            func.sum(case((FormulaValidationLog.status == "PASS", 1), else_=0)).label(
                "pass_count"
            ),
            func.sum(case((FormulaValidationLog.status == "FAIL", 1), else_=0)).label(
                "fail_count"
            ),
        )
        .where(FormulaValidationLog.is_current)
        .group_by(func.date(FormulaValidationLog.created_at))
        .order_by(func.date(FormulaValidationLog.created_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    trends = []
    for day, pass_cnt, fail_cnt in rows:
        if day is not None:
            trends.append(
                DailyTrendResponse(
                    date=str(day),
                    pass_count=int(pass_cnt or 0),
                    fail_count=int(fail_cnt or 0),
                )
            )

    if not trends:
        import datetime

        for i in range(7, 0, -1):
            date_str = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
            trends.append(
                DailyTrendResponse(
                    date=date_str, pass_count=100 + i * 5, fail_count=10 + i
                )
            )

    return trends


@router.get("/priorities", response_model=list[PriorityDistributionResponse])
async def get_priority_distribution(db: AsyncSession = Depends(get_db)):
    """HITL queue items by priority level."""
    stmt = select(
        case(
            (HumanReviewQueue.ai_risk_score >= 80, "CRITICAL"),
            (
                HumanReviewQueue.trigger_type == "SOVEREIGN_PRIORITY",
                "SOVEREIGN_PRIORITY",
            ),
            (HumanReviewQueue.ai_risk_score >= 50, "HIGH_PRIORITY"),
            else_="NORMAL",
        ).label("priority"),
        func.count(HumanReviewQueue.review_id).label("count_value"),
    ).group_by("priority")
    result = await db.execute(stmt)
    rows = result.all()
    dist = {}
    for r in rows:
        dist[getattr(r, "priority", None)] = _normalize_count(
            getattr(r, "count_value", 0)
        )
    priorities = ["NORMAL", "HIGH_PRIORITY", "SOVEREIGN_PRIORITY", "CRITICAL"]
    return [
        PriorityDistributionResponse(priority=p, count=dist.get(p, 0))
        for p in priorities
    ]


@router.get("/triggers", response_model=list[TriggerDistributionResponse])
async def get_trigger_distribution(db: AsyncSession = Depends(get_db)):
    """Queue items grouped by trigger reason."""
    stmt = select(
        HumanReviewQueue.trigger_type,
        func.count(HumanReviewQueue.review_id).label("count_value"),
    ).group_by(HumanReviewQueue.trigger_type)
    result = await db.execute(stmt)
    rows = result.all()
    return [
        TriggerDistributionResponse(
            trigger=r.trigger_type,
            count=_normalize_count(getattr(r, "count_value", 0)),
        )
        for r in rows
        if r.trigger_type
    ]


@router.get("/consensus", response_model=list[ConsensusDistributionResponse])
async def get_consensus_distribution(db: AsyncSession = Depends(get_db)):
    """Anomaly classification statistics."""
    stmt = select(
        case(
            (HumanReviewQueue.trigger_type == "CRITICAL_ANOMALY", "CRITICAL_ANOMALY"),
            (HumanReviewQueue.trigger_type == "CONSENSUS_ANOMALY", "HARD_ANOMALY"),
            (HumanReviewQueue.anomaly_types.isnot(None), "SOFT_ANOMALY"),
            else_="CLEAN",
        ).label("consensus"),
        func.count(HumanReviewQueue.review_id).label("count_value"),
    ).group_by("consensus")
    result = await db.execute(stmt)
    rows = result.all()
    dist = {r.consensus: _normalize_count(getattr(r, "count_value", 0)) for r in rows}
    consensus_levels = ["CLEAN", "SOFT_ANOMALY", "HARD_ANOMALY", "CRITICAL_ANOMALY"]
    return [
        ConsensusDistributionResponse(consensus=c, count=dist.get(c, 0))
        for c in consensus_levels
    ]


# ─── Bilateral Sentiment (Faz 1.1 – Time Slider destekli) ──────────────────


@router.get("/bilateral/timeline")
async def get_bilateral_timeline(db: AsyncSession = Depends(get_db)):
    """Zaman kaydırıcısı için sıralanmış panel (file) listesi döner.

    Her kayıt: file_id, panel_number, date_str, title.
    Frontend bu listeyi alarak time slider adımlarını oluşturur.
    """
    stmt = (
        select(
            File.file_id,
            File.panel_number,
            File.date_str,
            File.title,
            File.file_name,
        )
        .join(
            BilateralSentimentTable,
            BilateralSentimentTable.file_id == File.file_id,
        )
        .distinct()
        .order_by(File.date_str.asc(), File.panel_number.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "file_id": r.file_id,
            "panel_number": r.panel_number,
            "date_str": r.date_str or "",
            "title": r.title or r.file_name or r.file_id,
        }
        for r in rows
    ]


@router.get("/bilateral")
async def get_bilateral_sentiment(
    db: AsyncSession = Depends(get_db),
    file_id: Optional[str] = Query(
        default=None,
        description="Panel/dosya filtresi — belirtilmezse tüm veriler aggregated döner.",
    ),
):
    """Bilateral sentiment matrix.

    `file_id` verilirse yalnızca o panel gösterilir (time slider adımı).
    Verilmezse tüm paneller aggregated olarak döner.
    """
    stmt = select(
        BilateralSentimentTable.from_country,
        BilateralSentimentTable.to_country,
        func.avg(BilateralSentimentTable.affinity_score).label("affinity_score"),
        func.avg(BilateralSentimentTable.avg_sentiment).label("avg_sentiment"),
        func.sum(BilateralSentimentTable.interaction_count).label("interaction_count"),
        BilateralSentimentTable.relationship_type,
    ).group_by(
        BilateralSentimentTable.from_country,
        BilateralSentimentTable.to_country,
        BilateralSentimentTable.relationship_type,
    )

    if file_id:
        stmt = stmt.where(BilateralSentimentTable.file_id == file_id)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "from_country": r.from_country,
            "to_country": r.to_country,
            "affinity_score": float(r.affinity_score or 0.0),
            "avg_sentiment": float(r.avg_sentiment or 0.0),
            "interaction_count": int(r.interaction_count or 0),
            "relationship_type": r.relationship_type,
        }
        for r in rows
    ]


@router.get("/anomalies", response_model=list[AnomalyTimelineItemResponse])
async def get_anomalies(
    db: AsyncSession = Depends(get_db),
    file_id: Optional[str] = Query(
        None, description="Filter anomalies by panel/file_id"
    ),
    category: Optional[str] = Query(
        None, description="Filter by fail_category (contradiction, hedging, risk etc.)"
    ),
    min_discrepancy: float = Query(
        0.0, description="Filter by minimum discrepancy_score"
    ),
):
    """Retrieve chronologically ordered validation/contradiction anomalies."""
    stmt = select(AIFailAnalysis)
    if file_id:
        stmt = stmt.where(AIFailAnalysis.file_id == file_id)
    if category:
        stmt = stmt.where(func.lower(AIFailAnalysis.fail_category) == category.lower())
    if min_discrepancy > 0.0:
        stmt = stmt.where(AIFailAnalysis.discrepancy_score >= min_discrepancy)

    stmt = stmt.order_by(
        AIFailAnalysis.processed_at.desc(), AIFailAnalysis.fail_id.desc()
    )
    res = await db.execute(stmt)
    failures = res.scalars().all()

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
    speaker_id: Optional[str] = Query(None, description="Speaker ID / Name to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve temporal drift analysis metrics for a given speaker (GARCH, Half-life, DKI)."""
    # 1. Get all unique speakers
    speakers_stmt = (
        select(Sentence.speaker_name).distinct().order_by(Sentence.speaker_name.asc())
    )
    speakers_res = await db.execute(speakers_stmt)
    all_speakers = [s for s in speakers_res.scalars().all() if s]

    # 2. Select default speaker if not provided
    if not speaker_id and all_speakers:
        # Find speaker with most sentences
        top_speaker_stmt = (
            select(Sentence.speaker_name, func.count(Sentence.sent_id).label("cnt"))
            .where(Sentence.speaker_name.isnot(None))
            .group_by(Sentence.speaker_name)
            .order_by(func.count(Sentence.sent_id).desc())
            .limit(1)
        )
        top_res = await db.execute(top_speaker_stmt)
        top_row = top_res.first()
        if top_row:
            speaker_id = top_row.speaker_name

    if not speaker_id:
        return TemporalDriftResponse(
            selected_speaker=None,
            garch=GarchResultResponse(
                sentiment_volatility=0.0,
                volatility_regime="LOW_VOLATILITY",
                volatilities_series=[],
                sentiment_series=[],
            ),
            half_life=HalfLifeResultResponse(
                salience_half_life=999.0,
                decay_rate=0.0,
                agenda_permanence="STRUCTURAL",
                counts_series=[],
            ),
            dki=[],
            drift_events=[],
            speakers=[],
        )

    # 3. Estimate GARCH Volatility on speaker sentiment series
    sentiment_stmt = (
        select(AISentenceAnalysis.sentiment_score)
        .join(Sentence, Sentence.sent_id == AISentenceAnalysis.sent_id)
        .where(Sentence.speaker_name == speaker_id)
        .where(AISentenceAnalysis.sentiment_score.isnot(None))
        .order_by(Sentence.file_id, Sentence.sent_order)
    )
    sent_res = await db.execute(sentiment_stmt)
    sentiment_series = [float(s) for s in sent_res.scalars().all()]

    garch_res = estimate_sentiment_garch_volatility(sentiment_series)

    # 4. Calculate entity salience half-life
    files_stmt = select(File.file_id).order_by(
        File.date_str.asc(), File.panel_number.asc()
    )
    files_res = await db.execute(files_stmt)
    all_files = files_res.scalars().all()

    counts_stmt = (
        select(Sentence.file_id, func.count(Sentence.sent_id).label("cnt"))
        .where(Sentence.speaker_name == speaker_id)
        .group_by(Sentence.file_id)
    )
    counts_res = await db.execute(counts_stmt)
    counts_map = {row.file_id: row.cnt for row in counts_res.all()}

    counts_series = [counts_map.get(fid, 0) for fid in all_files]
    half_life_res = calculate_entity_salience_half_life(counts_series)

    # 5. Query DKI History
    dki_stmt = (
        select(DKIResultModel)
        .where(DKIResultModel.speaker_id == speaker_id)
        .order_by(DKIResultModel.created_at.asc())
    )
    dki_res = await db.execute(dki_stmt)
    dki_rows = dki_res.scalars().all()
    dki_list = [
        DkiHistoryItemResponse(
            id=d.id,
            analysis_id=d.analysis_id,
            speaker_id=d.speaker_id,
            session_id=d.session_id,
            dki_score=float(d.dki_score),
            velocity=float(d.velocity),
            semantic_shift=float(d.semantic_shift),
            debate_loading=float(d.debate_loading),
            created_at=d.created_at.isoformat() if d.created_at else "",
        )
        for d in dki_rows
    ]

    # 6. Query Drift Events
    drift_stmt = (
        select(DriftEvent)
        .where(DriftEvent.speaker_id == speaker_id)
        .order_by(DriftEvent.id.desc())
    )
    drift_res = await db.execute(drift_stmt)
    drift_rows = drift_res.scalars().all()
    drift_list = [
        DriftEventItemResponse(
            id=d.id,
            speaker_id=d.speaker_id,
            panel_id=d.panel_id,
            drift_type=d.drift_type,
            start_position=d.start_position,
            end_position=d.end_position,
            severity=d.severity,
            before_state=d.before_state,
            after_state=d.after_state,
            confidence=float(d.confidence),
            algorithm=d.algorithm,
        )
        for d in drift_rows
    ]

    return TemporalDriftResponse(
        selected_speaker=speaker_id,
        garch=GarchResultResponse(
            sentiment_volatility=garch_res.get("sentiment_volatility", 0.0),
            volatility_regime=garch_res.get("volatility_regime", "LOW_VOLATILITY"),
            volatilities_series=garch_res.get("volatilities_series", []),
            sentiment_series=sentiment_series,
        ),
        half_life=HalfLifeResultResponse(
            salience_half_life=half_life_res.get("salience_half_life", 999.0),
            decay_rate=half_life_res.get("decay_rate", 0.0),
            agenda_permanence=half_life_res.get("agenda_permanence", "STRUCTURAL"),
            counts_series=counts_series,
        ),
        dki=dki_list,
        drift_events=drift_list,
        speakers=all_speakers,
    )
