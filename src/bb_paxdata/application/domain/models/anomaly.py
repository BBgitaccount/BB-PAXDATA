from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bb_paxdata.application.domain.utils.json_validation import validate_json_safe

from ..enums import AnomalySeverity, AnomalyType, EvidenceType, RiskLevel


class Anomaly(BaseModel):
    """Represents an anomaly detected in the conversation analysis."""

    id: str = Field(..., description="Unique identifier for the anomaly")
    segment_id: str | None = Field(
        default=None, description="ID of the segment where anomaly was detected"
    )
    sentence_id: str | None = Field(
        default=None, description="ID of the sentence where anomaly was detected"
    )
    speaker_id: str | None = Field(
        default=None, description="ID of the speaker associated with anomaly"
    )

    # Anomaly classification
    anomaly_type: AnomalyType = Field(..., description="Type of anomaly detected")
    severity: AnomalySeverity = Field(..., description="Severity level of the anomaly")

    # Detection information
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in anomaly detection"
    )
    detection_method: str | None = Field(
        default=None, description="Method used for detection"
    )
    detector_version: str | None = Field(
        default=None, description="Version of the detection algorithm"
    )

    # Evidence and context
    evidence_types: list[EvidenceType] = Field(
        default_factory=list, description="Types of evidence supporting the anomaly"
    )
    evidence_text: str | None = Field(
        default=None, description="Textual evidence of the anomaly"
    )
    context_window: str | None = Field(
        default=None, description="Context around the anomaly"
    )

    # Temporal information
    detection_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When anomaly was detected",
    )
    occurrence_time: float | None = Field(
        default=None, description="Time when anomaly occurred in seconds"
    )

    # Analysis and impact
    impact_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Impact score of the anomaly"
    )
    risk_contribution: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Contribution to overall risk"
    )

    # Related anomalies
    related_anomaly_ids: list[str] = Field(
        default_factory=list, description="IDs of related anomalies"
    )
    is_clustered: bool = Field(
        default=False, description="Whether this anomaly is part of a cluster"
    )
    cluster_id: str | None = Field(
        default=None, description="ID of the cluster if applicable"
    )

    # Status and resolution
    is_resolved: bool = Field(
        default=False, description="Whether anomaly has been resolved"
    )
    resolution_method: str | None = Field(
        default=None, description="Method used for resolution"
    )
    resolution_timestamp: datetime | None = Field(
        default=None, description="When anomaly was resolved"
    )

    # Notes and explanations
    description: str | None = Field(
        default=None, description="Description of the anomaly"
    )
    explanation: str | None = Field(
        default=None, description="Detailed explanation of why this is an anomaly"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommended actions"
    )

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: dict[str, Any] | None = Field(
        default_factory=lambda: {}, description="Additional metadata"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp",
    )

    @model_validator(mode="after")
    def validate_json_fields(self) -> Anomaly:
        """Ensure metadata contains only JSON-safe types."""
        if self.metadata is not None:
            try:
                validate_json_safe(self.metadata)
            except TypeError as e:
                raise ValueError(f"Invalid metadata: {e}")
        return self


class AnomalyValidationDecision(str, Enum):
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"
    ESCALATED = "ESCALATED"
    AI_ONLY = "AI_ONLY"
    INCONCLUSIVE = "INCONCLUSIVE"


class AnomalyValidationResult(BaseModel):
    """AIAnomalyController çıktısı — domain modeli."""

    model_config = ConfigDict(frozen=False)

    decision: AnomalyValidationDecision
    coherence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    detected_subtype: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    raw_llm_response: str = ""


class RuleIndicator(BaseModel):
    value: str


class AnomalyResult(BaseModel):
    """Canonical AnomalyResult for CrossAnomalyService.detect() output.

    This is the single canonical AnomalyResult class used throughout the application.
    Legacy AnomalyResult from application.protocols is deprecated.
    """

    score: float = Field(
        default=0.0, ge=0.0, le=1.5, description="Anomaly score [0.0, 1.5]"
    )
    flags: list[str] = Field(
        default_factory=list, description="Triggered rule messages"
    )
    risk_level: RiskLevel = Field(default=RiskLevel.NONE, description="Risk level")
    triggered_count: int = Field(default=0, description="Number of triggered rules")

    # Fields for backward/forward compatibility
    triggered_rules: list[RuleIndicator] = Field(default_factory=list)
    anomaly_score: float = 0.0
    confidence: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def sync_compatibility_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If built with old fields, populate the new fields
            if "anomaly_score" in data and "score" not in data:
                data["score"] = data["anomaly_score"]
            if "triggered_rules" in data and "flags" not in data:
                rules = data["triggered_rules"]
                # triggered_rules can be list[RuleIndicator] or list[dict] or list[str]
                flags = []
                for r in rules:
                    if isinstance(r, dict):
                        flags.append(r.get("value", ""))
                    elif hasattr(r, "value"):
                        flags.append(r.value)
                    else:
                        flags.append(str(r))
                data["flags"] = flags

            # If built with new fields, populate compatibility fields
            if "score" in data and "anomaly_score" not in data:
                data["anomaly_score"] = data["score"]
            if "flags" in data and "triggered_rules" not in data:
                data["triggered_rules"] = [
                    RuleIndicator(value=f) for f in data["flags"]
                ]

            if "flags" in data and "triggered_count" not in data:
                data["triggered_count"] = len(data["flags"])
        return data

    @property
    def has_anomaly(self) -> bool:
        return (
            self.score > 0.0
            or self.triggered_count > 0
            or len(self.triggered_rules) > 0
        )


class ContradictionResult(BaseModel):
    """Result details of advanced contradiction checks."""

    score: float
    threshold: float
    is_anomaly: bool
    anomaly_type: AnomalyType
    n_sentences: int
    m1: float
    m2: float
    theta: float
    window: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_json_fields(self) -> ContradictionResult:
        """Ensure metadata contains only JSON-safe types."""
        try:
            validate_json_safe(self.metadata)
        except TypeError as e:
            raise ValueError(f"Invalid metadata: {e}")
        return self

    def extend_metadata(self, new_meta: dict[str, Any]) -> None:
        self.metadata.update(new_meta)
