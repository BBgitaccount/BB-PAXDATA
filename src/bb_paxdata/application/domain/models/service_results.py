"""Service result schemas for BB-PAXDATA.

This module defines Pydantic models for service outputs to prevent circular dependencies.
"""

from typing import Any

from pydantic import BaseModel, Field

from ..enums import (
    AnomalySeverity,
    AnomalyType,
    AppraisalAttitude,
    AudienceType,
    EvidenceType,
    FrameType,
    HedgeType,
    RiskLevel,
    SentimentCategory,
    TopicCategory,
)
from .risk_signal import RiskSignal


class HedgingResult(BaseModel):
    """Result of hedging analysis."""

    score: float = Field(..., ge=0.0, le=1.0, description="Hedging score from 0 to 1")
    categories: list[HedgeType] = Field(
        default_factory=list, description="Detected hedging categories"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class SentimentResult(BaseModel):
    """Result of sentiment analysis."""

    score: float = Field(
        ..., ge=-1.0, le=1.0, description="Sentiment score from -1 to 1"
    )
    emotion_category: SentimentCategory = Field(..., description="Emotion category")
    negation_aware_score: float = Field(
        ..., ge=-1.0, le=1.0, description="Negation-aware sentiment score"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )
    liwc_scores: dict[str, float] | None = Field(
        default=None,
        description="LIWC2015 proxy scores (clout, analytic, authenticity, tone)",
    )


class RiskAssessment(BaseModel):
    """Result of risk assessment."""

    sbi_score: float = Field(..., description="Söylemsel Baskı İndeksi score")
    dki_score: float = Field(..., description="Diplomatik Konum İndeksi score")
    risk_score: float = Field(..., ge=0.0, le=10.0, description="Overall risk score")
    risk_signals: list[RiskSignal] = Field(
        default_factory=list, description="Detected risk signals"
    )
    severity: RiskLevel = Field(..., description="Risk severity level")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class FrameResult(BaseModel):
    """Result of frame detection."""

    frame_type: FrameType = Field(..., description="Detected frame type")
    evidence_types: list[EvidenceType] = Field(
        default_factory=list, description="Evidence types used"
    )
    appraisal_attitude: AppraisalAttitude = Field(..., description="Appraisal attitude")
    audience_type: AudienceType = Field(..., description="Target audience type")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class TopicAnalysis(BaseModel):
    """Result of topic analysis."""

    topic_scores: dict[str, float] = Field(
        ..., description="Topic scores for each category"
    )
    dominant_topic: TopicCategory = Field(..., description="Dominant topic category")
    specificity: float = Field(
        ..., ge=0.0, le=1.0, description="Topic specificity score"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )


class AnomalyResult(BaseModel):
    """Result of anomaly detection."""

    type: AnomalyType = Field(..., description="Type of anomaly")
    severity: AnomalySeverity = Field(..., description="Severity level")
    category: str = Field(..., description="Anomaly category")
    description: str = Field(..., description="Description of the anomaly")
    ai_values: dict[str, Any] = Field(
        default_factory=dict, description="AI-derived values"
    )
    formula_values: dict[str, Any] = Field(
        default_factory=dict, description="Formula-derived values"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )
