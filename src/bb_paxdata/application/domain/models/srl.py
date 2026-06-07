"""
Semantic Role Labeling Domain Models
PropBank-compliant predicate-argument structures with enterprise-grade validation.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ArgumentType(str, Enum):
    """PropBank argument type taxonomy."""

    ARG0 = "ARG0"  # Agent/Proto-Agent
    ARG1 = "ARG1"  # Patient/Proto-Patient
    ARG2 = "ARG2"  # Instrument/Beneficiary
    ARG3 = "ARG3"  # Starting Point/Endpoint
    ARG4 = "ARG4"  # Endpoint
    ARGM_LOC = "ARGM-LOC"  # Location
    ARGM_TMP = "ARGM-TMP"  # Temporal
    ARGM_MOD = "ARGM-MOD"  # Modal
    ARGM_NEG = "ARGM-NEG"  # Negation
    ARGM_CAU = "ARGM-CAU"  # Causal
    ARGM_MNR = "ARGM-MNR"  # Manner
    ARGM_EXT = "ARGM-EXT"  # Extent


class SRLSpan(BaseModel):
    """
    Character-level span representation with validation.

    Invariant: start_char <= end_char
    Invariant: text length == end_char - start_char
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Normalized substring text of the argument",
        examples=["Turkey", "the proposal"],
    )
    start_char: int = Field(
        ..., ge=0, description="Character-level start offset (inclusive)"
    )
    end_char: int = Field(
        ..., ge=0, description="Character-level end offset (exclusive)"
    )

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        """Normalize whitespace and control characters."""
        return " ".join(v.split()).strip()

    @model_validator(mode="after")
    def validate_span_invariants(self) -> SRLSpan:
        """Enforce span consistency constraints."""
        if self.start_char > self.end_char:
            raise ValueError(
                f"Span invariant violated: start_char ({self.start_char}) > "
                f"end_char ({self.end_char})"
            )

        expected_length = self.end_char - self.start_char
        if len(self.text) != expected_length:
            raise ValueError(
                f"Span text length mismatch: expected {expected_length}, "
                f"got {len(self.text)} for text='{self.text}'"
            )

        return self

    @property
    def char_span(self) -> tuple[int, int]:
        """Return as tuple for database storage."""
        return (self.start_char, self.end_char)


class SRLArgument(BaseModel):
    """
    Typed argument wrapper with confidence scoring.
    """

    argument_type: ArgumentType
    span: SRLSpan
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Model confidence score for this argument assignment",
    )

    @property
    def text(self) -> str:
        return self.span.text


class SRLFrame(BaseModel):
    """
    Complete PropBank semantic frame with full argument structure.
    """

    verb: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Predicate lemma or surface form",
        examples=["reject", "support", "sign"],
    )
    verb_lemma: str | None = Field(
        default=None, description="Lemmatized form of the predicate (if available)"
    )

    # Core arguments (Numbered Args)
    arg0: SRLSpan | None = Field(
        default=None, description="Proto-Agent / Actor (who performed the action)"
    )
    arg1: SRLSpan | None = Field(
        default=None, description="Proto-Patient / Target (what was affected)"
    )
    arg2: SRLSpan | None = Field(default=None, description="Instrument / Beneficiary")

    # Modifier arguments (Adjuncts - ARGM-*)
    argm_mod: str | None = Field(
        default=None, description="Modal auxiliary (might, will, must, should, can)"
    )
    argm_neg: bool = Field(
        default=False, description="Negation flag (True if action is negated)"
    )
    argm_tmp: SRLSpan | None = Field(
        default=None, description="Temporal modifier (when did it happen)"
    )
    argm_cau: SRLSpan | None = Field(
        default=None, description="Causal modifier (why did it happen)"
    )
    argm_loc: SRLSpan | None = Field(
        default=None, description="Location modifier (where did it happen)"
    )
    argm_mnr: SRLSpan | None = Field(
        default=None, description="Manner modifier (how did it happen)"
    )

    # Metadata
    frame_confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Overall frame extraction confidence"
    )
    source_sentence_idx: int | None = Field(
        default=None, ge=0, description="Index of source sentence in document"
    )

    @field_validator("verb")
    @classmethod
    def normalize_verb(cls, v: str) -> str:
        """Lowercase and strip verb."""
        return v.lower().strip()

    @property
    def has_complete_triplet(self) -> bool:
        """Check if frame contains Actor→Action→Target triplet."""
        return self.arg0 is not None and self.arg1 is not None

    @property
    def is_negated(self) -> bool:
        """Alias for negation check."""
        return self.argm_neg

    @property
    def actor_text(self) -> str | None:
        """Convenience accessor for ARG0 text."""
        return self.arg0.text if self.arg0 else None

    @property
    def target_text(self) -> str | None:
        """Convenience accessor for ARG1 text."""
        return self.arg1.text if self.arg1 else None

    def to_triplet(self) -> tuple[str, str, str] | None:
        """
        Extract Actor→Verb→Target triplet if complete.

        Returns:
            Tuple of (actor, verb, target) or None if incomplete.
        """
        if self.arg0 is not None and self.arg1 is not None:
            return (self.arg0.text, self.verb, self.arg1.text)
        return None

    def to_dict_for_db(self) -> dict:
        """
        Serialize to dictionary suitable for JSONB/Text DB columns.
        Optimized for DiscourseNetworkEdge storage.
        """
        return {
            "predicate": self.verb,
            "arg0_entity": self.actor_text,
            "arg1_entity": self.target_text,
            "argm_mod": self.argm_mod,
            "argm_neg": self.argm_neg,
            "argm_tmp": self.argm_tmp.text if self.argm_tmp else None,
            "confidence": self.frame_confidence,
        }


class SRLDocumentResult(BaseModel):
    """
    Container for all SRL frames extracted from a document.
    Provides aggregation statistics and quality metrics.
    """

    document_id: str | None = Field(default=None)
    frames: list[SRLFrame] = Field(default_factory=list)
    total_sentences_processed: int = Field(default=0, ge=0)
    total_frames_extracted: int = Field(default=0, ge=0)
    extraction_timestamp: float = Field(
        default_factory=lambda: __import__("time").time()
    )
    model_version: str = Field(default="dl22/bert-base-srl")
    processing_time_ms: float = Field(default=0.0, ge=0)

    @property
    def complete_triplets(self) -> list[tuple[str, str, str]]:
        """Extract all complete Actor→Action→Target triplets."""
        triplets = [
            frame.to_triplet() for frame in self.frames if frame.has_complete_triplet
        ]
        return [t for t in triplets if t is not None]

    @property
    def unique_predicates(self) -> set[str]:
        """Get set of unique predicates in document."""
        return {frame.verb for frame in self.frames}

    @property
    def frame_density(self) -> float:
        """Calculate frames per sentence ratio."""
        if self.total_sentences_processed == 0:
            return 0.0
        return self.total_frames_extracted / self.total_sentences_processed

    def get_frames_by_verb(self, verb: str) -> list[SRLFrame]:
        """Filter frames by specific verb (case-insensitive)."""
        verb_lower = verb.lower()
        return [f for f in self.frames if f.verb == verb_lower]


class ExtractionStatus(str, Enum):
    """SRL extraction lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # No predicates detected
