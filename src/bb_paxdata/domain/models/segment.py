from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..enums import (
    AudienceType,
    ContextualImportance,
    DynamicEvent,
    EvidenceType,
    FrameType,
    SentimentArc,
    TemporalPattern,
    TopicCategory,
)
from .lodp_result import LODPResult
from .risk_signal import RiskSignal
from .sentence import Sentence


class TemporalSegmentAnalysis(BaseModel):
    """Intro / develop / conclusion sentiment arc for a stored segment row."""

    segment_id: str = Field(..., description="Segment identifier")
    intro_sentiment: float = Field(..., description="Intro-phase sentiment")
    develop_sentiment: float = Field(..., description="Development-phase sentiment")
    concl_sentiment: float = Field(..., description="Conclusion-phase sentiment")
    risk_trend: str | None = Field(default=None, description="Risk trend label")
    risk_trajectory: str | None = Field(
        default=None, description="Risk trajectory label"
    )


class Segment(BaseModel):
    """Represents a segment of conversation containing multiple sentences."""

    id: str = Field(..., description="Unique identifier for the segment")
    panel_id: str | None = Field(
        default=None,
        description="Owning panel when persisting or loading from storage",
    )
    sentences: list[Sentence] = Field(
        default_factory=list, description="List of sentences in this segment"
    )

    # Temporal information
    start_time: float | None = Field(default=None, description="Start time in seconds")
    end_time: float | None = Field(default=None, description="End time in seconds")
    duration: float | None = Field(default=None, description="Duration in seconds")

    # Segment classification
    topic_category: TopicCategory | None = Field(
        default=None, description="Primary topic category"
    )
    contextual_importance: ContextualImportance | None = Field(
        default=None, description="Contextual importance level"
    )
    temporal_pattern: TemporalPattern | None = Field(
        default=None, description="Temporal pattern type"
    )
    dynamic_event: DynamicEvent | None = Field(
        default=None, description="Dynamic event classification"
    )

    # Sentiment analysis
    sentiment_arc: SentimentArc | None = Field(
        default=None, description="Sentiment progression pattern"
    )
    avg_sentiment_score: float | None = Field(
        default=None, ge=-1.0, le=1.0, description="Average sentiment score"
    )

    # Speaker information
    speaker: Any | None = Field(default=None, description="Speaker object")
    primary_speaker_id: str | None = Field(
        default=None, description="ID of the primary speaker"
    )
    speaker_count: int | None = Field(
        default=None, ge=0, description="Number of unique speakers"
    )

    # Content metrics
    word_count: int | None = Field(default=None, ge=0, description="Total word count")
    sentence_count: int | None = Field(
        default=None, ge=0, description="Number of sentences"
    )

    # Analytic Scores (v5.8 Parity)
    sbi_score: float | None = Field(
        default=None, description="Discursive Pressure Index (SBI)"
    )
    dki_score: float | None = Field(
        default=None, description="Diplomatic Position Index (DKI)"
    )
    risk_score: int = Field(default=0, description="Aggregated risk score")
    risk_signals: list[RiskSignal] = Field(
        default_factory=list, description="Detected risk signals"
    )
    risk_trajectory: str | None = Field(
        default=None, description="Risk trajectory (ESCALATING, etc.)"
    )
    demand_concentration: dict[str, int] | None = Field(
        default=None, description="Demand count by section"
    )
    demand_count: int = Field(default=0, description="Total demand count")

    # Mode results (Dominant categories)
    dominant_frame: FrameType | None = Field(
        default=None, description="Most frequent frame type"
    )
    dominant_audience: AudienceType | None = Field(
        default=None, description="Most frequent audience type"
    )
    dominant_evidence: EvidenceType | None = Field(
        default=None, description="Most frequent evidence type"
    )
    dominant_topic: TopicCategory | None = Field(
        default=None, description="Most frequent topic"
    )
    emotion_category: str | None = Field(
        default=None, description="Most frequent emotion category"
    )

    # Aggregated metrics
    vader_compound: float | None = Field(
        default=None, description="Average VADER compound score"
    )
    avg_hedging_score: float | None = Field(
        default=None, description="Average hedging score"
    )
    formula_manip_score: float | None = Field(
        default=None, description="Aggregated manipulation score"
    )

    @property
    def text(self) -> str:
        """Segment içindeki tüm cümlelerin birleştirilmiş metni."""
        return " ".join(s.text for s in self.sentences)

    @property
    def escalated_risk_score(self) -> float:
        """Zagare (2004) escalation multiplier'lı risk skoru.

        BaseRisk = lexical_risk_density × severity_weight (assumed to be risk_score here)
        RiskScore = BaseRisk × max(EscalationMultiplier_i)
        """
        if not self.risk_signals:
            return float(self.risk_score)

        max_multiplier = max(s.escalation_multiplier for s in self.risk_signals)
        weighted_sum = sum(s.weighted_risk_contribution for s in self.risk_signals)

        # Zagare formülü: BaseRisk × max_multiplier + weighted_contributions
        return (float(self.risk_score) * max_multiplier) + (weighted_sum * 0.1)

    # Lodp & Key phrases
    tokens: list[str] = Field(default_factory=list, description="Tokenized text")
    key_concepts: list[str] = Field(
        default_factory=list, description="Extracted key concepts (Faz 4/5/6)"
    )
    key_phrases: list[str] = Field(
        default_factory=list, description="Distinctive words/phrases"
    )
    lodp_results: list[LODPResult] | None = Field(
        default=None, description="Monroe LODP analysis results"
    )
    negation_density: float = Field(
        default=0.0, ge=0.0, description="Negation cues per token"
    )

    # Metadata
    summary: str | None = Field(
        default=None, description="Brief summary of segment content"
    )
    confidence_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence score of analysis"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )
