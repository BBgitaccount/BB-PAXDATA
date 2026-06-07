from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..enums import ContextualImportance, EvidenceType, TopicCategory


class Topic(BaseModel):
    """Represents a topic or subject discussed in the conversation."""

    id: str = Field(..., description="Unique identifier for the topic")
    segment_id: str | None = Field(
        default=None, description="ID of the segment where topic was discussed"
    )
    speaker_id: str | None = Field(
        default=None, description="ID of the speaker who introduced the topic"
    )

    # Topic classification
    topic_category: TopicCategory = Field(
        ..., description="Primary category of the topic"
    )
    subcategory: str | None = Field(
        default=None, description="More specific subcategory"
    )
    contextual_importance: ContextualImportance | None = Field(
        default=None, description="Importance of the topic in context"
    )

    # Content and context
    topic_name: str = Field(..., description="Name or title of the topic")
    topic_description: str | None = Field(
        default=None, description="Description of the topic"
    )
    key_terms: list[str] = Field(
        default_factory=list, description="Key terms associated with the topic"
    )
    context: str | None = Field(
        default=None, description="Context of the topic discussion"
    )

    # Temporal information
    first_mention_time: float | None = Field(
        default=None, description="Time of first mention in seconds"
    )
    last_mention_time: float | None = Field(
        default=None, description="Time of last mention in seconds"
    )
    duration: float | None = Field(
        default=None, description="Total duration of topic discussion"
    )

    # Analysis metrics
    prominence_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Prominence of the topic"
    )
    controversy_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Level of controversy"
    )
    complexity_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Complexity of the topic"
    )
    sentiment_score: float | None = Field(
        default=None, ge=-1.0, le=1.0, description="Sentiment associated with the topic"
    )

    # Evidence and confidence
    evidence_types: list[EvidenceType] = Field(
        default_factory=list,
        description="Types of evidence supporting topic identification",
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in topic identification"
    )

    # Topic relationships
    parent_topic_id: str | None = Field(
        default=None, description="ID of parent topic if this is a subtopic"
    )
    related_topic_ids: list[str] = Field(
        default_factory=list, description="IDs of related topics"
    )
    conflicting_topic_ids: list[str] = Field(
        default_factory=list, description="IDs of conflicting topics"
    )

    # Participation and engagement
    participating_speakers: list[str] = Field(
        default_factory=list, description="IDs of speakers who participated"
    )
    speaker_engagement: dict[str, float] = Field(
        default_factory=dict, description="Engagement level per speaker"
    )
    audience_reception: str | None = Field(
        default=None, description="Audience reception of the topic"
    )

    # Topic evolution
    evolution_pattern: str | None = Field(
        default=None, description="How the topic evolved during discussion"
    )
    resolution_status: str | None = Field(
        default=None, description="Resolution status of the topic"
    )
    outcome: str | None = Field(
        default=None, description="Outcome or decision related to the topic"
    )

    # Impact assessment
    impact_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Impact score on the conversation"
    )
    action_items: list[str] = Field(
        default_factory=list, description="Action items resulting from topic discussion"
    )

    # Status and lifecycle
    is_active: bool = Field(
        default=True, description="Whether topic is still being discussed"
    )
    is_resolved: bool = Field(
        default=False, description="Whether topic has been resolved"
    )
    is_contentious: bool = Field(
        default=False, description="Whether topic is contentious"
    )

    # Notes and metadata
    analysis_notes: str | None = Field(
        default=None, description="Notes from topic analysis"
    )
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: dict[str, Any] | None = Field(
        default_factory=lambda: {}, description="Additional metadata"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )


class TopicAssignment(BaseModel):
    """Assignment of topics to a specific segment."""

    segment_id: str = Field(..., description="ID of the segment")
    primary_topic: str = Field(..., description="ID of the dominant topic")
    topic_scores: dict[str, float] = Field(
        default_factory=dict, description="Probabilistic distribution of topics"
    )


class TopicResult(BaseModel):
    """Aggregated results from the topic modeling service."""

    assignments: list[TopicAssignment] = Field(
        default_factory=list, description="List of topic assignments for each segment"
    )
    topic_keywords: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Top keywords for each topic with c-TF-IDF scores",
    )
    model_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata about the topic modeling process"
    )
