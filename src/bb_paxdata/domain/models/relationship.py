from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..enums import EvidenceType, InfluenceTier, PressureTier, RelationshipType


class Relationship(BaseModel):
    """Represents a relationship between speakers or entities in the conversation."""

    id: str = Field(..., description="Unique identifier for the relationship")
    speaker_a_id: str = Field(..., description="ID of the first speaker/entity")
    speaker_b_id: str = Field(..., description="ID of the second speaker/entity")

    # Relationship classification
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    relationship_status: str | None = Field(
        default=None, description="Current status of the relationship"
    )
    relationship_nature: str | None = Field(
        default=None, description="Nature of the relationship (formal, informal, etc.)"
    )

    # Power dynamics
    power_balance: str | None = Field(
        default=None, description="Power balance description"
    )
    influence_a_to_b: InfluenceTier | None = Field(
        default=None, description="Influence of speaker A on B"
    )
    influence_b_to_a: InfluenceTier | None = Field(
        default=None, description="Influence of speaker B on A"
    )
    pressure_a_on_b: PressureTier | None = Field(
        default=None, description="Pressure exerted by A on B"
    )
    pressure_b_on_a: PressureTier | None = Field(
        default=None, description="Pressure exerted by B on A"
    )

    # Interaction patterns
    interaction_frequency: str | None = Field(
        default=None, description="Frequency of interactions"
    )
    communication_style: str | None = Field(
        default=None, description="Communication style between entities"
    )
    conflict_level: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Level of conflict in relationship"
    )
    cooperation_level: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Level of cooperation"
    )

    # Evidence and confidence
    evidence_types: list[EvidenceType] = Field(
        default_factory=list,
        description="Types of evidence supporting relationship identification",
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in relationship identification"
    )

    # Temporal information
    relationship_start: float | None = Field(
        default=None, description="When relationship was first observed"
    )
    relationship_duration: float | None = Field(
        default=None, description="Duration of relationship observation"
    )
    last_interaction: float | None = Field(
        default=None, description="Time of last interaction"
    )

    # Emotional and social aspects
    emotional_tone: str | None = Field(
        default=None, description="Emotional tone of the relationship"
    )
    trust_level: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Level of trust between entities"
    )
    respect_level: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Level of respect between entities"
    )

    # Context and environment
    relationship_context: str | None = Field(
        default=None, description="Context in which relationship exists"
    )
    environmental_factors: list[str] = Field(
        default_factory=list, description="Environmental factors affecting relationship"
    )

    # Evolution and changes
    relationship_evolution: str | None = Field(
        default=None, description="How relationship has evolved"
    )
    change_indicators: list[str] = Field(
        default_factory=list, description="Indicators of relationship change"
    )
    trajectory: str | None = Field(
        default=None, description="Projected trajectory of relationship"
    )

    # Impact and consequences
    impact_on_conversation: str | None = Field(
        default=None, description="Impact on conversation dynamics"
    )
    consequences: list[str] = Field(
        default_factory=list, description="Consequences of the relationship"
    )

    # Related relationships
    related_relationship_ids: list[str] = Field(
        default_factory=list, description="IDs of related relationships"
    )
    group_affiliations: list[str] = Field(
        default_factory=list, description="Shared group affiliations"
    )

    # Status and lifecycle
    is_active: bool = Field(
        default=True, description="Whether relationship is currently active"
    )
    is_formal: bool = Field(default=False, description="Whether relationship is formal")
    is_hierarchical: bool = Field(
        default=False, description="Whether relationship is hierarchical"
    )

    # Notes and metadata
    analysis_notes: str | None = Field(
        default=None, description="Notes from relationship analysis"
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
