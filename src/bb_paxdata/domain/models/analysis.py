from datetime import datetime

from pydantic import BaseModel, Field

from ..enums import (
    AnomalySeverity,
    AnomalyType,
    EvidenceType,
    FailCategory,
    FutureRiskTier,
    RiskLevel,
    RiskTrajectory,
    ValidationCheckType,
)


class Analysis(BaseModel):
    """Represents analysis results for a segment or sentence with various assessments.

    Includes risk, sentiment, and anomaly assessments.
    """

    id: str = Field(..., description="Unique identifier for the analysis")
    segment_id: str | None = Field(default=None, description="ID of analyzed segment")
    sentence_id: str | None = Field(default=None, description="ID of analyzed sentence")
    speaker_id: str | None = Field(
        default=None, description="ID of the speaker analyzed"
    )

    # Risk assessment
    risk_level: RiskLevel = Field(..., description="Current risk level")
    risk_trajectory: RiskTrajectory | None = Field(
        default=None, description="Risk trajectory trend"
    )
    future_risk_tier: FutureRiskTier | None = Field(
        default=None, description="Projected future risk tier"
    )

    # Sentiment and emotional metrics
    sentiment_score: float = Field(
        ..., ge=-1.0, le=1.0, description="Sentiment score from -1 to 1"
    )
    emotional_intensity: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Emotional intensity score"
    )
    stress_level: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Stress level indicator"
    )

    # Anomaly detection
    anomalies: list[AnomalySeverity] = Field(
        default_factory=list, description="List of detected anomaly severities"
    )
    anomaly_types: list[AnomalyType] = Field(
        default_factory=list, description="Types of anomalies detected"
    )
    anomaly_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence in anomaly detection"
    )

    # Validation results
    validation_checks: dict[ValidationCheckType, bool] = Field(
        default_factory=dict, description="Validation check results"
    )
    validation_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Overall validation score"
    )
    fail_category: FailCategory | None = Field(
        default=None, description="Category of validation failures"
    )

    # Evidence and confidence
    evidence_types: list[EvidenceType] = Field(
        default_factory=list, description="Types of evidence found"
    )
    evidence_strength: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Strength of evidence"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence score"
    )

    # Additional metrics
    complexity_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Complexity score"
    )
    coherence_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Coherence score"
    )
    manipulation_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Manipulation likelihood score"
    )

    # Analysis metadata
    analysis_version: str = Field(
        default="1.0", description="Version of analysis methodology"
    )
    analysis_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When analysis was performed"
    )
    analyzer_id: str | None = Field(
        default=None, description="ID of analyzer system or analyst"
    )

    # Notes and explanations
    sumcomplexity_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Complexity score"
    )
    detailed_findings: str | None = Field(
        default=None, description="Detailed analysis findings"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommended actions based on analysis"
    )

    # [FAZ3] PromptRegistry entegrasyonu
    prompt_version: str | None = Field(
        default=None,
        description=(
            "Bu analizi üretmek için kullanılan prompt'un versiyonu. "
            "Format: '{prompt_name}:{version}:{hash}' "
            "Örnek: 'sentence_analysis:v1.0:a3f9b2c1e8d47f20'"
        ),
        examples=["sentence_analysis:v1.0:a3f9b2c1e8d47f20"],
    )


# Alias for compatibility with instructions
SentenceAnalysis = Analysis


class SegmentInsight(BaseModel):
    # [FAZ3] PromptRegistry entegrasyonu
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )


class DemandAnalysis(BaseModel):
    # [FAZ3] PromptRegistry entegrasyonu
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )


class PanelSynthesis(BaseModel):
    # [FAZ3] PromptRegistry entegrasyonu
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )


class FailCheckAnalysis(BaseModel):
    # [FAZ3] PromptRegistry entegrasyonu
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )
