from typing import Any, Optional

from pydantic import BaseModel, Field


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
