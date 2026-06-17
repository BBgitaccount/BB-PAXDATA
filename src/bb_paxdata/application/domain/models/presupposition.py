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


class PresuppositionCandidate(BaseModel):
    """Candidate presupposition for verification."""

    model_config = ConfigDict(frozen=False)

    trigger_word: str = Field(..., description="The trigger word/phrase")
    trigger_type: TriggerType = Field(..., description="Type of presupposition trigger")
    presupposed_content: str = Field(..., description="The presupposed content")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    segment_id: str = Field(..., description="ID of the source segment")
    speaker: str = Field(..., description="Speaker who uttered the text")
    segment_text: str = Field(..., description="Full text of the segment")
    timestamp: float | None = Field(
        default=None, description="Timestamp of the utterance"
    )

    @classmethod
    def calculate_confidence(
        cls,
        trigger_lemma: str,
        presupposed_content: str,
        sentence_length: int,
    ) -> float:
        """
        Calculate base confidence for a presupposition candidate.
        Uses trigger-specific specificity weights (Lewis 1979 / Beaver & Geurts 2014).
        """
        specificity_weights = {
            "regret": 0.90,
            "acknowledge": 0.85,
            "fail": 0.82,
            "manage": 0.80,
            "realize": 0.70,
            "still": 0.68,
            "again": 0.65,
            "know": 0.60,
            "start": 0.50,
            "stop": 0.50,
            "continue": 0.55,
        }

        lemma = trigger_lemma.lower()
        specificity = specificity_weights.get(lemma, 0.50)

        # Parse completeness check
        parse_completeness = 1.0 if presupposed_content else 0.0

        # Context check (simple heuristic)
        context_score = 0.5 if sentence_length > 3 else 0.3

        # Confidence formula: base + specificity*0.2 + parse*0.2 + context*0.1
        confidence = (
            0.5
            + (specificity * 0.2)
            + (parse_completeness * 0.2)
            + (context_score * 0.1)
        )

        return min(confidence, 1.0)
