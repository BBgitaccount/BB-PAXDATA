from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.use_cases.compare_sessions import (
    CompareSessionsInput,
    CompareSessionsUseCase,
)
from bb_paxdata.infrastructure.db.repositories.analysis import AnalysisRepository
from bb_paxdata.infrastructure.db.repositories.country_repository import (
    BilateralSentimentRepository,
    DiscourseFlowRepository,
)
from bb_paxdata.infrastructure.db.repositories.dki_repository import DKIRepository
from bb_paxdata.infrastructure.db.repositories.sbi_repository import SBIRepository
from bb_paxdata.interfaces.api.dependencies import PermissionChecker, get_db
from bb_paxdata.interfaces.api.schemas import (
    AnalysisDeltaResponse,
    CompareSessionsRequest,
    CompareSessionsResponse,
    ContrastReportResponse,
    NarrativeLayerDeltaResponse,
    SignificantChangeResponse,
    SpeechActDeltaResponse,
)

router = APIRouter(prefix="/compare", tags=["comparison"])

# Authoritative URLs:
#   POST /api/v1/compare/sessions
#   GET  /api/v1/compare/sessions/available


def get_compare_use_case(
    db: AsyncSession = Depends(get_db),
) -> CompareSessionsUseCase:
    """Dependency provider for CompareSessionsUseCase."""

    # Import here to avoid circular imports
    from bb_paxdata.application.domain.services.ai_analyst import AIAnalyst
    from bb_paxdata.config.settings import settings

    llm_service = (
        AIAnalyst(
            model=getattr(settings, "COMPARISON_NARRATIVE_MODEL", "gpt-4o-mini"),
            max_tokens=getattr(settings, "COMPARISON_NARRATIVE_MAX_TOKENS", 1000),
        )
        if getattr(settings, "COMPARISON_NARRATIVE_ENABLED", True)
        else None
    )

    return CompareSessionsUseCase(
        sbi_repository=SBIRepository(db),
        dki_repository=DKIRepository(db),
        analysis_repository=AnalysisRepository(db),
        bilateral_repository=BilateralSentimentRepository(db),
        discourse_repository=DiscourseFlowRepository(db),
        llm_service=llm_service,
    )


def _build_analysis_delta_response(delta) -> AnalysisDeltaResponse:
    """Convert domain AnalysisDelta to API response schema."""
    return AnalysisDeltaResponse(
        session_a_id=delta.session_a_id,
        session_b_id=delta.session_b_id,
        comparison_timestamp=delta.comparison_timestamp.isoformat(),
        delta_sbi=delta.delta_sbi,
        delta_sbi_normalized=delta.delta_sbi_normalized,
        delta_sbi_significant=delta.delta_sbi_significant,
        delta_dki=delta.delta_dki,
        delta_dki_normalized=delta.delta_dki_normalized,
        delta_dki_significant=delta.delta_dki_significant,
        delta_risk=delta.delta_risk,
        delta_risk_normalized=delta.delta_risk_normalized,
        delta_risk_significant=delta.delta_risk_significant,
        delta_hedging=delta.delta_hedging,
        delta_hedging_normalized=delta.delta_hedging_normalized,
        delta_hedging_significant=delta.delta_hedging_significant,
        delta_speech_act={
            k: SpeechActDeltaResponse(
                speaker_id=v.speaker_id,
                distribution_a=v.distribution_a,
                distribution_b=v.distribution_b,
                delta_distribution=v.delta_distribution,
                most_changed_type=v.most_changed_type,
                change_magnitude=v.change_magnitude,
            )
            for k, v in delta.delta_speech_act.items()
        },
        delta_narrative={
            k: NarrativeLayerDeltaResponse(
                speaker_id=v.speaker_id,
                layer_weights_a=v.layer_weights_a,
                layer_weights_b=v.layer_weights_b,
                delta_weights=v.delta_weights,
                dominant_layer_change=v.dominant_layer_change,
            )
            for k, v in delta.delta_narrative.items()
        },
        significant_changes=[
            SignificantChangeResponse(
                dimension=c.dimension,
                speaker_id=c.speaker_id,
                raw_delta=c.raw_delta,
                normalized_delta=c.normalized_delta,
            )
            for c in delta.significant_changes
        ],
        speakers_in_a=sorted(delta.speakers_in_a),
        speakers_in_b=sorted(delta.speakers_in_b),
        common_speakers=sorted(delta.common_speakers),
        speakers_only_in_a=sorted(delta.speakers_only_in_a),
        speakers_only_in_b=sorted(delta.speakers_only_in_b),
        most_drifted_speaker=delta.most_drifted_speaker,
        most_drifted_dimension=delta.most_drifted_dimension,
        total_significant_changes=delta.total_significant_changes,
    )


def _build_contrast_report_response(report) -> ContrastReportResponse:
    """Convert domain ContrastReport to API response schema."""
    delta_response = _build_analysis_delta_response(report.delta)

    return ContrastReportResponse(
        report_id=report.report_id,
        delta=delta_response,
        narrative_summary=report.narrative_summary,
        narrative_summary_skipped=report.narrative_summary_skipped,
        narrative_summary_failed=report.narrative_summary_failed,
        narrative_summary_model=report.narrative_summary_model,
        narrative_summary_timestamp=(
            report.narrative_summary_timestamp.isoformat()
            if report.narrative_summary_timestamp
            else None
        ),
        most_drifted_speaker=report.most_drifted_speaker,
        most_drifted_dimension=report.most_drifted_dimension,
        key_insights=report.key_insights,
        risk_assessment=(
            report.risk_assessment.value if report.risk_assessment else None
        ),
        risk_level_changed=report.risk_level_changed,
        recommendation=report.recommendation,
        generated_at=report.generated_at.isoformat(),
    )


def _build_response(output) -> CompareSessionsResponse:
    """Build CompareSessionsResponse from CompareSessionsOutput."""
    contrast_report_response = None
    analysis_delta_response = None

    if output.contrast_report:
        contrast_report_response = _build_contrast_report_response(
            output.contrast_report
        )

    if output.analysis_delta:
        analysis_delta_response = _build_analysis_delta_response(output.analysis_delta)

    return CompareSessionsResponse(
        success=output.success,
        contrast_report=contrast_report_response,
        analysis_delta=analysis_delta_response,
        errors=list(output.errors),
    )


@router.post("/sessions", response_model=CompareSessionsResponse)
async def compare_sessions(
    request: CompareSessionsRequest,
    use_case: CompareSessionsUseCase = Depends(get_compare_use_case),
    _has_permission: bool = Depends(PermissionChecker("create_comparison")),
) -> CompareSessionsResponse:
    """Compare two sessions/panels and generate contrast report."""

    input_data = CompareSessionsInput(
        session_a_id=request.session_a_id,
        session_b_id=request.session_b_id,
        sbi_threshold=request.sbi_threshold,
        dki_threshold=request.dki_threshold,
        risk_threshold=request.risk_threshold,
        hedging_threshold=request.hedging_threshold,
        include_narrative=request.include_narrative,
        narrative_language=request.narrative_language,
    )

    output = await use_case.execute(input_data)

    if not output.succeeded:
        raise HTTPException(
            status_code=500,
            detail={
                "fatal_errors": list(output.fatal_errors),
                "errors": list(output.errors),
            },
        )

    return _build_response(output)


@router.get("/sessions/available")
async def list_available_sessions(
    db: AsyncSession = Depends(get_db),
    _has_permission: bool = Depends(PermissionChecker("view_comparison")),
) -> dict:
    """List all available session/panel IDs for comparison."""

    sbi_repo = SBIRepository(db)
    stmt = select(func.distinct(sbi_repo.model_class.session_id)).order_by(
        sbi_repo.model_class.session_id
    )
    result = await db.execute(stmt)
    session_ids = [row[0] for row in result.all()]

    return {"session_ids": session_ids}
