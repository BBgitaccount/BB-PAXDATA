from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..enums import DkiStance, EvidenceType, FrameType


class Frame(BaseModel):
    """Represents a framing device or rhetorical frame used in the conversation."""

    id: str = Field(..., description="Unique identifier for the frame")
    segment_id: str | None = Field(
        None, description="ID of the segment where frame was detected"
    )
    sentence_id: str | None = Field(
        None, description="ID of the sentence containing the frame"
    )
    speaker_id: str = Field(..., description="ID of the speaker using the frame")

    # Frame classification
    frame_type: FrameType = Field(..., description="Type of frame used")
    dki_stance: DkiStance | None = Field(None, description="DKI stance classification")

    # Content and context
    frame_text: str = Field(..., description="Exact text of the framed content")
    frame_elements: list[str] = Field(
        default_factory=list, description="Key elements of the frame"
    )
    context: str | None = Field(None, description="Context surrounding the frame")

    # Temporal information
    timestamp: float | None = Field(
        None, description="Time when frame was used in seconds"
    )
    duration: float | None = Field(
        None, description="Duration of the framing in seconds"
    )

    # Analysis metrics
    effectiveness_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Effectiveness of the frame"
    )
    persuasiveness_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Persuasiveness level"
    )
    emotional_appeal: float | None = Field(
        None, ge=0.0, le=1.0, description="Emotional appeal strength"
    )
    logical_appeal: float | None = Field(
        None, ge=0.0, le=1.0, description="Logical appeal strength"
    )

    # Evidence and confidence
    evidence_types: list[EvidenceType] = Field(
        default_factory=list,
        description="Types of evidence supporting frame identification",
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in frame identification"
    )

    # Target and impact
    target_audience: str | None = Field(None, description="Intended target audience")
    target_concept: str | None = Field(None, description="Concept being framed")
    impact_assessment: str | None = Field(
        None, description="Assessment of frame impact"
    )

    # Relationships and patterns
    related_frame_ids: list[str] = Field(
        default_factory=list, description="IDs of related frames"
    )
    is_counter_frame: bool = Field(
        default=False, description="Whether this is a counter-frame"
    )
    parent_frame_id: str | None = Field(
        None, description="ID of parent frame if this is a response"
    )

    # Linguistic features
    metaphors_used: list[str] = Field(
        default_factory=list, description="Metaphors used in the frame"
    )
    loaded_terms: list[str] = Field(
        default_factory=list, description="Loaded or biased terms used"
    )
    emotional_triggers: list[str] = Field(
        default_factory=list, description="Emotional triggers employed"
    )

    # Strategic purpose
    strategic_goal: str | None = Field(None, description="Strategic goal of the frame")
    intended_effect: str | None = Field(None, description="Intended effect on audience")

    # Status and lifecycle
    is_active: bool = Field(
        default=True, description="Whether frame is still active in conversation"
    )
    effectiveness_confirmed: bool = Field(
        default=False, description="Whether effectiveness has been confirmed"
    )

    # Notes and metadata
    analysis_notes: str | None = Field(None, description="Notes from frame analysis")
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
