from datetime import datetime

from pydantic import BaseModel, Field

from ..enums import (
    ContextualImportance,
    DynamicEvent,
    SentimentArc,
    TemporalPattern,
    TopicCategory,
)
from .sentence import Sentence


class Segment(BaseModel):
    """Represents a segment of conversation containing multiple sentences."""

    id: str = Field(..., description="Unique identifier for the segment")
    sentences: list[Sentence] = Field(
        default_factory=list, description="List of sentences in this segment"
    )

    # Temporal information
    start_time: float | None = Field(None, description="Start time in seconds")
    end_time: float | None = Field(None, description="End time in seconds")
    duration: float | None = Field(None, description="Duration in seconds")

    # Segment classification
    topic_category: TopicCategory | None = Field(
        None, description="Primary topic category"
    )
    contextual_importance: ContextualImportance | None = Field(
        None, description="Contextual importance level"
    )
    temporal_pattern: TemporalPattern | None = Field(
        None, description="Temporal pattern type"
    )
    dynamic_event: DynamicEvent | None = Field(
        None, description="Dynamic event classification"
    )

    # Sentiment analysis
    sentiment_arc: SentimentArc | None = Field(
        None, description="Sentiment progression pattern"
    )
    avg_sentiment_score: float | None = Field(
        None, ge=-1.0, le=1.0, description="Average sentiment score"
    )

    # Speaker information
    primary_speaker_id: str | None = Field(
        None, description="ID of the primary speaker"
    )
    speaker_count: int | None = Field(
        None, ge=0, description="Number of unique speakers"
    )

    # Content metrics
    word_count: int | None = Field(None, ge=0, description="Total word count")
    sentence_count: int | None = Field(None, ge=0, description="Number of sentences")

    # Metadata
    summary: str | None = Field(None, description="Brief summary of segment content")
    confidence_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence score of analysis"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
