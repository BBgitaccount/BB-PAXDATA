from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..enums import AnomalySeverity, AnomalyType, EvidenceType


class Anomaly(BaseModel):
    """Represents an anomaly detected in the conversation analysis."""

    id: str = Field(..., description="Unique identifier for the anomaly")
    segment_id: str | None = Field(
        None, description="ID of the segment where anomaly was detected"
    )
    sentence_id: str | None = Field(
        None, description="ID of the sentence where anomaly was detected"
    )
    speaker_id: str | None = Field(
        None, description="ID of the speaker associated with anomaly"
    )

    # Anomaly classification
    anomaly_type: AnomalyType = Field(..., description="Type of anomaly detected")
    severity: AnomalySeverity = Field(..., description="Severity level of the anomaly")

    # Detection information
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in anomaly detection"
    )
    detection_method: str | None = Field(None, description="Method used for detection")
    detector_version: str | None = Field(
        None, description="Version of the detection algorithm"
    )

    # Evidence and context
    evidence_types: list[EvidenceType] = Field(
        default_factory=list, description="Types of evidence supporting the anomaly"
    )
    evidence_text: str | None = Field(
        None, description="Textual evidence of the anomaly"
    )
    context_window: str | None = Field(None, description="Context around the anomaly")

    # Temporal information
    detection_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When anomaly was detected"
    )
    occurrence_time: float | None = Field(
        None, description="Time when anomaly occurred in seconds"
    )

    # Analysis and impact
    impact_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Impact score of the anomaly"
    )
    risk_contribution: float | None = Field(
        None, ge=0.0, le=1.0, description="Contribution to overall risk"
    )

    # Related anomalies
    related_anomaly_ids: list[str] = Field(
        default_factory=list, description="IDs of related anomalies"
    )
    is_clustered: bool = Field(
        default=False, description="Whether this anomaly is part of a cluster"
    )
    cluster_id: str | None = Field(None, description="ID of the cluster if applicable")

    # Status and resolution
    is_resolved: bool = Field(
        default=False, description="Whether anomaly has been resolved"
    )
    resolution_method: str | None = Field(
        None, description="Method used for resolution"
    )
    resolution_timestamp: datetime | None = Field(
        None, description="When anomaly was resolved"
    )

    # Notes and explanations
    description: str | None = Field(None, description="Description of the anomaly")
    explanation: str | None = Field(
        None, description="Detailed explanation of why this is an anomaly"
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
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
