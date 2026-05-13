from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Metadata(BaseModel):
    """Represents metadata for various entities in the system."""

    id: str = Field(..., description="Unique identifier for the metadata")
    entity_id: str = Field(..., description="ID of the entity this metadata belongs to")
    entity_type: str = Field(
        ..., description="Type of entity (transcript, segment, speaker, etc.)"
    )

    # Basic information
    title: str | None = Field(default=None, description="Title or name")
    description: str | None = Field(default=None, description="Detailed description")

    # Classification and tagging
    category: str | None = Field(default=None, description="Primary category")
    subcategory: str | None = Field(default=None, description="Secondary category")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    keywords: list[str] = Field(default_factory=list, description="Keywords for search")

    # Source and provenance
    source: str | None = Field(default=None, description="Source of the data")
    source_url: str | None = Field(
        default=None, description="URL of the source if applicable"
    )
    source_date: datetime | None = Field(
        default=None, description="Date of the source data"
    )

    # Quality and validation
    quality_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Quality score"
    )
    validation_status: str | None = Field(default=None, description="Validation status")
    last_validated: datetime | None = Field(
        default=None, description="Last validation timestamp"
    )

    # Processing information
    processed_by: str | None = Field(
        default=None, description="System or user that processed this"
    )
    processing_version: str | None = Field(
        default=None, description="Version of processing pipeline"
    )
    processing_parameters: dict[str, Any] | None = Field(
        default_factory=lambda: {}, description="Processing parameters used"
    )

    # Custom fields
    custom_fields: dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata fields"
    )
    annotations: list[str] = Field(
        default_factory=list, description="Human annotations or notes"
    )

    # Access and permissions
    access_level: str | None = Field(default=None, description="Access level required")
    is_public: bool = Field(
        default=False, description="Whether this metadata is public"
    )
    is_sensitive: bool = Field(
        default=False, description="Whether this contains sensitive information"
    )

    # Lifecycle
    is_active: bool = Field(default=True, description="Whether this metadata is active")
    is_archived: bool = Field(default=False, description="Whether this is archived")

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
    expires_at: datetime | None = Field(
        default=None, description="Expiration timestamp if applicable"
    )
