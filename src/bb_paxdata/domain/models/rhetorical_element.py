from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..enums import (
    DiplomaticTone,
    EvidenceType,
    PolitenessAct,
    RhetoricalStrategy,
    RhetoricPatternType,
)


class RhetoricalElement(BaseModel):
    """Represents a rhetorical element or pattern detected in the conversation."""

    id: str = Field(..., description="Unique identifier for the rhetorical element")
    segment_id: str | None = Field(
        None, description="ID of the segment where element was detected"
    )
    sentence_id: str | None = Field(
        None, description="ID of the sentence containing the element"
    )
    speaker_id: str = Field(
        ..., description="ID of the speaker using the rhetorical element"
    )

    # Rhetorical classification
    pattern_type: RhetoricPatternType = Field(
        ..., description="Type of rhetorical pattern"
    )
    strategy: RhetoricalStrategy = Field(..., description="Overall rhetorical strategy")
    politeness_act: PolitenessAct | None = Field(
        None, description="Politeness act classification"
    )
    diplomatic_tone: DiplomaticTone | None = Field(
        None, description="Diplomatic tone classification"
    )

    # Content and context
    element_text: str = Field(..., description="Exact text of the rhetorical element")
    pattern_structure: str | None = Field(
        None, description="Structure of the rhetorical pattern"
    )
    context: str | None = Field(None, description="Context surrounding the element")

    # Temporal information
    timestamp: float | None = Field(
        None, description="Time when element was used in seconds"
    )
    duration: float | None = Field(
        None, description="Duration of the rhetorical element"
    )

    # Analysis metrics
    effectiveness_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Effectiveness of the rhetorical element"
    )
    persuasiveness_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Persuasiveness level"
    )
    complexity_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Complexity of the rhetorical structure"
    )
    sophistication_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Sophistication level"
    )

    # Evidence and confidence
    evidence_types: list[EvidenceType] = Field(
        default_factory=list, description="Types of evidence supporting identification"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in rhetorical element identification",
    )

    # Target and purpose
    target_audience: str | None = Field(None, description="Intended target audience")
    intended_purpose: str | None = Field(
        None, description="Intended purpose of the rhetorical element"
    )
    emotional_target: str | None = Field(
        None, description="Emotional response being targeted"
    )

    # Relationships and patterns
    related_element_ids: list[str] = Field(
        default_factory=list, description="IDs of related rhetorical elements"
    )
    is_response_element: bool = Field(
        default=False, description="Whether this is a response to another element"
    )
    responding_to_id: str | None = Field(
        None, description="ID of element being responded to"
    )

    # Linguistic features
    rhetorical_devices: list[str] = Field(
        default_factory=list, description="Rhetorical devices used"
    )
    figurative_language: list[str] = Field(
        default_factory=list, description="Figurative language elements"
    )
    persuasive_techniques: list[str] = Field(
        default_factory=list, description="Persuasive techniques employed"
    )

    # Strategic context
    conversation_goal: str | None = Field(
        None, description="Goal within the conversation"
    )
    power_dynamics: str | None = Field(
        None, description="Power dynamics being addressed"
    )

    # Impact assessment
    audience_impact: str | None = Field(
        None, description="Assessment of audience impact"
    )
    conversation_impact: str | None = Field(
        None, description="Impact on conversation direction"
    )

    # Status and lifecycle
    is_successful: bool | None = Field(
        None, description="Whether the rhetorical element achieved its goal"
    )
    success_indicators: list[str] = Field(
        default_factory=list, description="Indicators of success"
    )

    # Notes and metadata
    analysis_notes: str | None = Field(
        None, description="Notes from rhetorical analysis"
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
