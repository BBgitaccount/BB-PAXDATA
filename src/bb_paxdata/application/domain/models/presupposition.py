"""
Presupposition Domain Models
Lewis (1979) Common Ground Theory; Beaver & Geurts (2014) Presupposition Triggers
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bb_paxdata.application.domain.models.srl import SRLSpan


class TriggerType(str, Enum):
    """Presupposition trigger type taxonomy."""

    FACTIVE_VERB = "FACTIVE_VERB"
    IMPLICATIVE_VERB = "IMPLICATIVE_VERB"
    TEMPORAL_ADVERB = "TEMPORAL_ADVERB"
    TEMPORAL_MULTIWORD = "TEMPORAL_MULTIWORD"
    CHANGE_OF_STATE = "CHANGE_OF_STATE"
    DEFINITE_NP = "DEFINITE_NP"
    CLEFT_CONSTRUCTION = "CLEFT_CONSTRUCTION"


class VerificationMethod(str, Enum):
    """Method used to verify a presupposition candidate."""

    RULE = "rule"
    LLM = "llm"
    HYBRID = "hybrid"


class Presupposition(BaseModel):
    """
    A single presupposition extracted from diplomatic discourse.
    Frozen Pydantic model for immutability and serialization consistency.
    """

    model_config = ConfigDict(frozen=True)

    trigger_word: str = Field(
        ..., description="The trigger word/phrase that induces the presupposition"
    )
    trigger_type: TriggerType = Field(..., description="Type of presupposition trigger")
    presupposed_content: str = Field(
        ..., description="The presupposed content (what is taken for granted)"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for the extraction"
    )
    segment_id: str = Field(..., description="ID of the source segment")
    speaker: str = Field(..., description="Speaker who uttered the presupposition")
    timestamp: float | None = Field(
        default=None, description="Timestamp of the utterance"
    )
    trigger_span: SRLSpan | None = Field(
        default=None, description="Character-level span of the trigger in the text"
    )
    verification_method: VerificationMethod | None = Field(
        default=None, description="Method used to verify this presupposition"
    )
    llm_confidence: float | None = Field(
        default=None, description="LLM verification confidence if applicable"
    )

    @field_validator("confidence", "llm_confidence", mode="before")
    @classmethod
    def validate_unit_interval(cls, v: float | None) -> float | None:
        """Ensure confidence scores are in [0.0, 1.0]."""
        if v is None:
            return v
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Score {v!r} outside [0.0, 1.0]")
        return v


class PresuppositionExtractionResult(BaseModel):
    """
    Result of presupposition extraction for a single segment/document.
    Frozen Pydantic model for consistency with other domain models.
    """

    model_config = ConfigDict(frozen=True)

    presuppositions: list[Presupposition] = Field(
        default_factory=list, description="List of extracted presuppositions"
    )
    total_triggers_found: int = Field(
        ..., ge=0, description="Total number of trigger words detected"
    )
    verified_count: int = Field(
        ..., ge=0, description="Number of presuppositions verified (LLM or hybrid)"
    )
    false_positive_filtered: int = Field(
        ..., ge=0, description="Number of candidates filtered as false positives"
    )
    processing_time_ms: float = Field(
        ..., ge=0.0, description="Total processing time in milliseconds"
    )
    language_detected: str = Field(
        default="en", description="Detected language of the text"
    )

    @property
    def precision_estimate(self) -> float:
        """Estimate precision based on verification results."""
        total_extracted = len(self.presuppositions) + self.false_positive_filtered
        if total_extracted == 0:
            return 1.0
        return len(self.presuppositions) / total_extracted

    @property
    def verification_rate(self) -> float:
        """Rate of candidates that underwent verification."""
        total = self.total_triggers_found
        if total == 0:
            return 0.0
        return self.verified_count / total
