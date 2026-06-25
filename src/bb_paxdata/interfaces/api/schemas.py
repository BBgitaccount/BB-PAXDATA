import re
from typing import Any

from pydantic import BaseModel, Field, model_validator


class KpiStatsResponse(BaseModel):
    total_logs: int
    total_pass: int
    total_fail: int
    total_anomalies: int
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
    details: dict[str, Any] | None = None
    human_verdict: str | None = None
    human_note: str | None = None
    log_version: int
    reviewer_id: str | None = None
    sentence_text: str | None = None
    sent_id: str | None = None
    seg_id: str | None = None
    file_id: str | None = None
    speaker_name: str | None = None
    country: str | None = None
    power_level: int
    ai_risk_score: int | None = None
    ai_emotion_category: str | None = None
    ai_diplomatic_tone: str | None = None
    review_id: int | None = None
    review_status: str | None = None
    trigger_type: str | None = None
    priority_score: float
    created_at: str | None = None


class SpeakerContext(BaseModel):
    name: str
    country: str
    role: str | None = None
    power_level: int
    influence_tier: str | None = None
    bloc: str | None = None


class PanelContext(BaseModel):
    file_id: str
    panel_number: int | None = None
    date: str | None = None
    theme: str | None = None


class TripletContextResponse(BaseModel):
    prev: str | None = None
    current: str | None = None
    next: str | None = None
    speaker: SpeakerContext | None = None
    panel: PanelContext | None = None


class CountryNode(BaseModel):
    country_code: str
    country_name: str
    latitude: float
    longitude: float
    total_mentions: int
    avg_sentiment: float


class CountryConnection(BaseModel):
    from_country: str
    to_country: str
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    avg_sentiment: float
    interaction_count: int
    relationship_type: str
    affinity_score: float


class WorldMapResponse(BaseModel):
    nodes: list[CountryNode]
    connections: list[CountryConnection]


class VerdictPayload(BaseModel):
    log_id: int = Field(..., gt=0)
    verdict: str = Field(..., pattern="^(CONFIRMED_PASS|CONFIRMED_FAIL|CORRECTED)$")
    corrected_value: float | None = Field(None, ge=-100.0, le=100.0)
    note: str | None = Field(None, max_length=2000)
    confidence: str | None = Field("MEDIUM", pattern="^(LOW|MEDIUM|HIGH)$")
    justification: str | None = Field(None, max_length=2000)
    reviewer_id: str = Field(..., min_length=1, max_length=100)


class VerdictResponse(BaseModel):
    new_log_id: int
    audit_id: int
    log_version: int


class SimilarCaseResponse(BaseModel):
    log_id: int
    entity_id: str
    actual_value: float
    human_verdict: str | None = None
    human_note: str | None = None
    sentence_text: str | None = None
    country: str | None = None
    speaker_name: str | None = None


class AuditEntryResponse(BaseModel):
    audit_id: int
    log_id: int
    action_type: str
    previous_verdict: str | None = None
    new_verdict: str
    previous_value: float | None = None
    new_value: float | None = None
    performed_by: str
    performed_at: str
    justification: str | None = None
    review_status: str | None = None


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
    file_id: str | None = None
    speaker_name: str | None = None
    country: str | None = None
    check_type: str
    formula_value: str | None = None
    ai_value: str | None = None
    discrepancy_score: float | None = None
    original_sentence: str | None = None
    fail_reason: str | None = None
    fail_category: str | None = None
    anomaly_types: str | None = None
    processed_at: str | None = None
    negation_type: str | None = None
    negation_scope: str | None = None
    linguistic_marker: str | None = None
    contextual_factor: str | None = None
    temporal_factor: str | None = None


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
    before_state: str | None = None
    after_state: str | None = None
    confidence: float
    algorithm: str


class TemporalDriftResponse(BaseModel):
    selected_speaker: str | None = None
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
    speaker_id: str | None = None
    raw_delta: float | None = None
    normalized_delta: float | None = None


class SpeechActDeltaResponse(BaseModel):
    speaker_id: str
    distribution_a: dict[str, float]
    distribution_b: dict[str, float]
    delta_distribution: dict[str, float]
    most_changed_type: str | None = None
    change_magnitude: float = 0.0


class NarrativeLayerDeltaResponse(BaseModel):
    speaker_id: str
    layer_weights_a: dict[str, float]
    layer_weights_b: dict[str, float]
    delta_weights: dict[str, float]
    dominant_layer_change: tuple[str, float] | None = None


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

    delta_risk: float | None = None
    delta_risk_normalized: float | None = None
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

    most_drifted_speaker: str | None = None
    most_drifted_dimension: str = ""
    total_significant_changes: int = 0


class ContrastReportResponse(BaseModel):
    report_id: str
    delta: AnalysisDeltaResponse

    narrative_summary: str | None = None
    narrative_summary_skipped: bool = False
    narrative_summary_failed: bool = False
    narrative_summary_model: str = ""
    narrative_summary_timestamp: str | None = None

    most_drifted_speaker: str | None = None
    most_drifted_dimension: str = ""

    key_insights: list[str] = Field(default_factory=list)
    risk_assessment: str | None = None
    risk_level_changed: bool = False
    recommendation: str | None = None

    generated_at: str


class CompareSessionsResponse(BaseModel):
    success: bool
    contrast_report: ContrastReportResponse | None = None
    analysis_delta: AnalysisDeltaResponse | None = None
    errors: list[str] = Field(default_factory=list)


class CalibrationReportResponse(BaseModel):
    id: str | int | None = None
    prompt_version: str
    evaluation_period_start: str
    evaluation_period_end: str
    cohens_kappa_frame: float | None = None
    cohens_kappa_risk: float | None = None
    ai_human_f1_frame: float | None = None
    ai_human_f1_risk: float | None = None
    sbi_mae: float | None = None
    total_reviews: int
    total_disagreements: int
    disagreement_rate: float
    is_reliable: bool
    requires_prompt_update: bool
    requires_weight_update: bool
    alert_message: str | None = None
    top_disagreement_patterns: list[str] = Field(default_factory=list)


class ReviewerResponse(BaseModel):
    reviewer_id: str
    scope_type: str
    scope_value: str
    permission_level: str
    max_daily_reviews: int
    current_daily_count: int
    is_active: bool
    created_at: str


class ReviewerPerformanceResponse(BaseModel):
    reviewer_id: str
    total_actions: int
    verdict_count: int
    correction_count: int
    correction_rate: float


class CalibrationTrendItem(BaseModel):
    month: str
    kappa: float
    f1: float


class SystemSettingsSchema(BaseModel):
    anomaly_soft_log_only: bool
    anomaly_controller_enabled: bool
    anomaly_context_window: int = Field(..., ge=1, le=50)
    risk_ai_weight: float = Field(..., ge=0.0, le=1.0)
    risk_anomaly_weight: float = Field(..., ge=0.0, le=1.0)
    formula_tolerance: float = Field(..., ge=0.0, le=0.5)
    risk_threshold: float = Field(..., ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_weights(self) -> "SystemSettingsSchema":
        if abs(self.risk_ai_weight + self.risk_anomaly_weight - 1.0) > 1e-6:
            raise ValueError("risk_ai_weight and risk_anomaly_weight must sum to 1.0")
        return self
