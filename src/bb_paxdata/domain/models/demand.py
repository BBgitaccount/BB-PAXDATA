from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..enums import DemandCategory, DemandType, EvidenceType, PressureTier


class Demand(BaseModel):
    """Represents a demand or request made during the conversation."""

    id: str = Field(..., description="Unique identifier for the demand")
    segment_id: str | None = Field(
        default=None, description="ID of the segment where demand was made"
    )
    sentence_id: str | None = Field(
        default=None, description="ID of the sentence containing the demand"
    )
    speaker_id: str = Field(..., description="ID of the speaker making the demand")
    target_speaker_id: str | None = Field(
        default=None, description="ID of the target speaker if applicable"
    )

    # Demand classification
    demand_type: DemandType = Field(..., description="Type of demand")
    demand_category: DemandCategory = Field(..., description="Category of the demand")
    pressure_level: PressureTier | None = Field(
        default=None, description="Pressure level of the demand"
    )

    # Content and context
    demand_text: str = Field(..., description="Exact text of the demand")
    paraphrased_demand: str | None = Field(
        default=None, description="Paraphrased version of the demand"
    )
    context: str | None = Field(
        default=None, description="Context surrounding the demand"
    )

    # Temporal information
    timestamp: float | None = Field(
        default=None, description="Time when demand was made in seconds"
    )
    urgency: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Urgency level of the demand"
    )
    deadline: float | None = Field(
        default=None, description="Deadline mentioned if any"
    )

    # Analysis metrics
    compliance_likelihood: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Likelihood of compliance"
    )
    assertiveness_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Assertiveness level"
    )
    politeness_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Politeness level"
    )

    # Evidence and confidence
    evidence_types: list[EvidenceType] = Field(
        default_factory=list,
        description="Types of evidence supporting demand identification",
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in demand identification"
    )

    # Response and outcome
    response_text: str | None = Field(
        default=None, description="Response to the demand"
    )
    response_timestamp: float | None = Field(
        default=None, description="Time of response"
    )
    compliance_status: str | None = Field(
        default=None,
        description="Compliance status (pending, accepted, rejected, etc.)",
    )

    # Relationships and dependencies
    related_demand_ids: list[str] = Field(
        default_factory=list, description="IDs of related demands"
    )
    is_conditional: bool = Field(
        default=False, description="Whether demand is conditional"
    )
    conditions: list[str] = Field(
        default_factory=list, description="Conditions attached to the demand"
    )

    # Impact assessment
    impact_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Impact score of the demand"
    )
    risk_implication: str | None = Field(
        default=None, description="Risk implications of the demand"
    )

    # Status and lifecycle
    is_active: bool = Field(default=True, description="Whether demand is still active")
    is_fulfilled: bool = Field(
        default=False, description="Whether demand has been fulfilled"
    )
    fulfillment_timestamp: datetime | None = Field(
        default=None, description="When demand was fulfilled"
    )

    # Notes and metadata
    notes: str | None = Field(
        default=None, description="Additional notes about the demand"
    )
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
