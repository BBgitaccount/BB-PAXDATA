from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..enums import BackendType, LogLevel
from .segment import Segment
from .speaker import Speaker


class Transcript(BaseModel):
    """Represents a complete transcript with all its components and metadata."""

    id: str = Field(..., description="Unique identifier for the transcript")
    title: str | None = Field(None, description="Title or name of the transcript")

    # Content components
    segments: list[Segment] = Field(
        default_factory=list, description="List of segments in the transcript"
    )
    speakers: list[Speaker] = Field(
        default_factory=list, description="List of speakers in the transcript"
    )

    # Temporal information
    start_time: float | None = Field(None, description="Start time in seconds")
    end_time: float | None = Field(None, description="End time in seconds")
    total_duration: float | None = Field(
        None, ge=0, description="Total duration in seconds"
    )
    recording_date: datetime | None = Field(
        None, description="Date of the original recording"
    )

    # Content metrics
    total_sentences: int | None = Field(
        None, ge=0, description="Total number of sentences"
    )
    total_words: int | None = Field(None, ge=0, description="Total word count")
    total_speakers: int | None = Field(
        None, ge=0, description="Total number of unique speakers"
    )

    # Processing information
    backend_type: BackendType | None = Field(
        None, description="Backend system used for processing"
    )
    processing_version: str | None = Field(
        None, description="Version of processing pipeline"
    )
    processing_date: datetime = Field(
        default_factory=datetime.utcnow, description="When transcript was processed"
    )

    # Quality and confidence
    overall_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Overall confidence score"
    )
    transcription_quality: float | None = Field(
        None, ge=0.0, le=1.0, description="Quality of transcription"
    )

    # Classification
    language: str | None = Field(None, description="Language of the transcript")
    domain: str | None = Field(
        None, description="Domain or context of the conversation"
    )
    classification: str | None = Field(
        None, description="Overall classification of the transcript"
    )

    # Metadata
    source_file: str | None = Field(None, description="Source file path or identifier")
    metadata: dict[str, Any] | None = Field(
        default_factory=lambda: {}, description="Additional metadata"
    )
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")

    # Logging and debugging
    log_level: LogLevel | None = Field(
        LogLevel.INFO, description="Logging level for this transcript"
    )
    processing_log: list[str] | None = Field(
        default_factory=lambda: [], description="Processing log entries"
    )

    # Status and lifecycle
    is_processed: bool = Field(
        default=False, description="Whether transcript has been fully processed"
    )
    is_validated: bool = Field(
        default=False, description="Whether transcript has passed validation"
    )
    is_archived: bool = Field(
        default=False, description="Whether transcript is archived"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
