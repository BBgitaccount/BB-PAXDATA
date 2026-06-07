from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ..enums import (
    AudienceType,
    BlocType,
    InfluenceTier,
    ManipulationTier,
    PressureTier,
    RelationshipType,
    SpeakerRole,
)


class Speaker(BaseModel):
    """Represents a speaker in the conversation with their characteristics and role."""

    id: str = Field(..., description="Unique identifier for the speaker")
    name: str = Field(..., description="Name or identifier of the speaker")
    role: SpeakerRole | None = Field(
        default=None, description="Role or position of the speaker"
    )

    # Classification and influence
    influence_tier: InfluenceTier | None = Field(
        default=None, description="Level of influence"
    )
    manipulation_tier: ManipulationTier | None = Field(
        default=None, description="Manipulation capability level"
    )
    pressure_tier: PressureTier | None = Field(
        default=None, description="Pressure exertion level"
    )

    # Group affiliations
    bloc_type: BlocType | None = Field(
        default=None, description="Bloc or group affiliation"
    )
    audience_type: AudienceType | None = Field(
        default=None, description="Audience classification"
    )

    # Relationship dynamics
    relationship_type: RelationshipType | None = Field(
        default=None, description="Relationship type with other parties"
    )

    # Speaking patterns
    total_sentences: int | None = Field(
        default=None, ge=0, description="Total number of sentences spoken"
    )
    total_words: int | None = Field(default=None, ge=0, description="Total word count")
    avg_sentence_length: float | None = Field(
        default=None, ge=0, description="Average sentence length"
    )
    speaking_percentage: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Percentage of total speaking time"
    )

    # Temporal information
    first_speech_time: float | None = Field(
        default=None, description="Time of first speech"
    )
    last_speech_time: float | None = Field(
        default=None, description="Time of last speech"
    )
    total_speaking_time: float | None = Field(
        default=None, ge=0, description="Total speaking time in seconds"
    )

    # Metadata
    description: str | None = Field(
        default=None, description="Additional description or notes"
    )
    confidence_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score of speaker identification",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )
