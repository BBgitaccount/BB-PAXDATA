import re
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class KpiStatsResponse(BaseModel):
    total_logs: int
    total_pass: int
    total_fail: int
    pending_review: int
    confirmed_fail: int
    confirmed_pass: int
    corrected: int
    accuracy_percentage: float


class FormulaHealthResponse(BaseModel):
    formula_name: str
    total_fail: int
    false_positive_rate: float
    correction_rate: float
    confirmed_fail_count: int
    false_positive_count: int
    correction_count: int


class DailyTrendResponse(BaseModel):
    date: str
    pass_count: int
    fail_count: int


class PriorityDistributionResponse(BaseModel):
    priority: str
    count: int


class TriggerDistributionResponse(BaseModel):
    trigger: str
    count: int


class ConsensusDistributionResponse(BaseModel):
    consensus: str
    count: int


class FailQueueItemResponse(BaseModel):
    log_id: int
    run_id: str
    formula_name: str
    status: str
    actual_value: float
    expected_constraint: str
    details: Optional[dict[str, Any]] = None
    human_verdict: Optional[str] = None
    human_note: Optional[str] = None
    log_version: int
    reviewer_id: Optional[str] = None
    sentence_text: Optional[str] = None
    sent_id: Optional[str] = None
    seg_id: Optional[str] = None
    file_id: Optional[str] = None
    speaker_name: Optional[str] = None
    country: Optional[str] = None
    power_level: int
    ai_risk_score: Optional[int] = None
    ai_emotion_category: Optional[str] = None
    ai_diplomatic_tone: Optional[str] = None
    review_id: Optional[int] = None
    review_status: Optional[str] = None
    trigger_type: Optional[str] = None
    priority_score: float
    created_at: Optional[str] = None


class SpeakerContext(BaseModel):
    name: str
    country: str
    role: Optional[str] = None
    power_level: int
    influence_tier: Optional[str] = None
    bloc: Optional[str] = None


class PanelContext(BaseModel):
    file_id: str
    panel_number: Optional[int] = None
    date: Optional[str] = None
    theme: Optional[str] = None


class TripletContextResponse(BaseModel):
    prev: Optional[str] = None
    current: Optional[str] = None
    next: Optional[str] = None
    speaker: Optional[SpeakerContext] = None
    panel: Optional[PanelContext] = None


class VerdictPayload(BaseModel):
    log_id: int
    verdict: str = Field(..., pattern="^(CONFIRMED_PASS|CONFIRMED_FAIL|CORRECTED)$")
    corrected_value: Optional[float] = None
    note: Optional[str] = None
    confidence: Optional[str] = Field("MEDIUM", pattern="^(LOW|MEDIUM|HIGH)$")
    justification: Optional[str] = None
    reviewer_id: str


class VerdictResponse(BaseModel):
    new_log_id: int
    audit_id: int
    log_version: int


class SimilarCaseResponse(BaseModel):
    log_id: int
    entity_id: str
    actual_value: float
    human_verdict: Optional[str] = None
    human_note: Optional[str] = None
    sentence_text: Optional[str] = None
    country: Optional[str] = None
    speaker_name: Optional[str] = None


class AuditEntryResponse(BaseModel):
    audit_id: int
    log_id: int
    action_type: str
    previous_verdict: Optional[str] = None
    new_verdict: str
    previous_value: Optional[float] = None
    new_value: Optional[float] = None
    performed_by: str
    performed_at: str
    justification: Optional[str] = None
    review_status: Optional[str] = None


class DiscourseNode(BaseModel):
    id: str
    label: str
    type: str


class DiscourseEdge(BaseModel):
    source: str
    target: str
    weight: float
    tf: float
    idf: float


class DiscourseNetworkResponse(BaseModel):
    nodes: list[DiscourseNode]
    edges: list[DiscourseEdge]


class DatabaseStatsResponse(BaseModel):
    database_mode: str
    size_bytes: int
    status: str
    row_counts: dict[str, int]


class AnomalyTimelineItemResponse(BaseModel):
    fail_id: int
    sent_id: str
    file_id: Optional[str] = None
    speaker_name: Optional[str] = None
    country: Optional[str] = None
    check_type: str
    formula_value: Optional[str] = None
    ai_value: Optional[str] = None
    discrepancy_score: Optional[float] = None
    original_sentence: Optional[str] = None
    fail_reason: Optional[str] = None
    fail_category: Optional[str] = None
    anomaly_types: Optional[str] = None
    processed_at: Optional[str] = None
    negation_type: Optional[str] = None
    negation_scope: Optional[str] = None
    linguistic_marker: Optional[str] = None
    contextual_factor: Optional[str] = None
    temporal_factor: Optional[str] = None


class GarchResultResponse(BaseModel):
    sentiment_volatility: float
    volatility_regime: str
    volatilities_series: list[float]
    sentiment_series: list[float]


class HalfLifeResultResponse(BaseModel):
    salience_half_life: float
    decay_rate: float
    agenda_permanence: str
    counts_series: list[int]


class DkiHistoryItemResponse(BaseModel):
    id: int
    analysis_id: str
    speaker_id: str
    session_id: str
    dki_score: float
    velocity: float
    semantic_shift: float
    debate_loading: float
    created_at: str


class DriftEventItemResponse(BaseModel):
    id: int
    speaker_id: str
    panel_id: str
    drift_type: str
    start_position: int
    end_position: int
    severity: str
    before_state: Optional[str] = None
    after_state: Optional[str] = None
    confidence: float
    algorithm: str


class TemporalDriftResponse(BaseModel):
    selected_speaker: Optional[str] = None
    garch: GarchResultResponse
    half_life: HalfLifeResultResponse
    dki: list[DkiHistoryItemResponse]
    drift_events: list[DriftEventItemResponse]
    speakers: list[str]


# Comparison schemas for TASK-E01
_LANG_CODE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")  # ISO 639-1 with optional region


class CompareSessionsRequest(BaseModel):
    session_a_id: str = Field(..., min_length=1, max_length=200)
    session_b_id: str = Field(..., min_length=1, max_length=200)
    sbi_threshold: float = Field(0.15, ge=0.0, le=1.0)
    dki_threshold: float = Field(0.15, ge=0.0, le=1.0)
    risk_threshold: float = Field(0.10, ge=0.0, le=1.0)
    hedging_threshold: float = Field(0.10, ge=0.0, le=1.0)
    include_narrative: bool = Field(True)
    narrative_language: str = Field("en", min_length=2, max_length=5)

    @model_validator(mode="after")
    def validate_fields(self) -> "CompareSessionsRequest":
        if self.session_a_id == self.session_b_id:
            raise ValueError("session_a_id and session_b_id must differ")
        if not _LANG_CODE_RE.match(self.narrative_language):
            raise ValueError(
                "narrative_language must be ISO 639-1 format (e.g. 'en', 'tr', 'fr')"
            )
        return self


class SignificantChangeResponse(BaseModel):
    dimension: str
    speaker_id: Optional[str] = None
    raw_delta: Optional[float] = None
    normalized_delta: Optional[float] = None


class SpeechActDeltaResponse(BaseModel):
    speaker_id: str
    distribution_a: dict[str, float]
    distribution_b: dict[str, float]
    delta_distribution: dict[str, float]
    most_changed_type: Optional[str] = None
    change_magnitude: float = 0.0


class NarrativeLayerDeltaResponse(BaseModel):
    speaker_id: str
    layer_weights_a: dict[str, float]
    layer_weights_b: dict[str, float]
    delta_weights: dict[str, float]
    dominant_layer_change: Optional[tuple[str, float]] = None


class AnalysisDeltaResponse(BaseModel):
    session_a_id: str
    session_b_id: str
    comparison_timestamp: str

    delta_sbi: dict[str, float] = Field(default_factory=dict)
    delta_sbi_normalized: dict[str, float] = Field(default_factory=dict)
    delta_sbi_significant: dict[str, bool] = Field(default_factory=dict)

    delta_dki: dict[str, float] = Field(default_factory=dict)
    delta_dki_normalized: dict[str, float] = Field(default_factory=dict)
    delta_dki_significant: dict[str, bool] = Field(default_factory=dict)

    delta_risk: Optional[float] = None
    delta_risk_normalized: Optional[float] = None
    delta_risk_significant: bool = False

    delta_hedging: dict[str, float] = Field(default_factory=dict)
    delta_hedging_normalized: dict[str, float] = Field(default_factory=dict)
    delta_hedging_significant: dict[str, bool] = Field(default_factory=dict)

    delta_speech_act: dict[str, SpeechActDeltaResponse] = Field(default_factory=dict)
    delta_narrative: dict[str, NarrativeLayerDeltaResponse] = Field(
        default_factory=dict
    )

    significant_changes: list[SignificantChangeResponse] = Field(default_factory=list)

    speakers_in_a: list[str] = Field(default_factory=list)
    speakers_in_b: list[str] = Field(default_factory=list)
    common_speakers: list[str] = Field(default_factory=list)
    speakers_only_in_a: list[str] = Field(default_factory=list)
    speakers_only_in_b: list[str] = Field(default_factory=list)

    most_drifted_speaker: Optional[str] = None
    most_drifted_dimension: str = ""
    total_significant_changes: int = 0


class ContrastReportResponse(BaseModel):
    report_id: str
    delta: AnalysisDeltaResponse

    narrative_summary: Optional[str] = None
    narrative_summary_skipped: bool = False
    narrative_summary_failed: bool = False
    narrative_summary_model: str = ""
    narrative_summary_timestamp: Optional[str] = None

    most_drifted_speaker: Optional[str] = None
    most_drifted_dimension: str = ""

    key_insights: list[str] = Field(default_factory=list)
    risk_assessment: Optional[str] = None
    risk_level_changed: bool = False
    recommendation: Optional[str] = None

    generated_at: str


class CompareSessionsResponse(BaseModel):
    success: bool
    contrast_report: Optional[ContrastReportResponse] = None
    analysis_delta: Optional[AnalysisDeltaResponse] = None
    errors: list[str] = Field(default_factory=list)
