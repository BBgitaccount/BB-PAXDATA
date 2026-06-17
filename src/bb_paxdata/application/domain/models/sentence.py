from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from bb_paxdata.application.domain.models.speech_act import SpeechActClassification
from bb_paxdata.application.domain.utils.hash import generate_sentence_code

from ..enums import (
    AppraisalAttitude,
    AudienceType,
    DiplomaticTone,
    EvidenceType,
    FrameType,
    HedgeType,
    NegationType,
    PolitenessAct,
    SentimentCategory,
    TensionLevel,
    TopicCategory,
)
from .base import AggregateRoot
from .negation_cue import NegationCue
from .srl import ExtractionStatus, SRLFrame


class Sentence(AggregateRoot):
    """Represents a single sentence in a transcript with analysis metadata."""

    id: str = Field(..., description="Unique identifier for the sentence")
    sentence_code: str = Field(
        default_factory=generate_sentence_code,
        description="Unique short code for the sentence",
    )
    text: str = Field(..., description="The actual text content of the sentence")
    speaker_id: str | None = Field(
        default=None, description="ID of the speaker who uttered this sentence"
    )
    segment_id: str | None = Field(
        default=None, description="ID of the segment this sentence belongs to"
    )
    speaker_name: str | None = Field(
        default=None, description="Name of the speaker who uttered this sentence"
    )
    country: str | None = Field(default=None, description="Country of the speaker")
    role: str | None = Field(default=None, description="Role of the speaker")
    bloc: str | None = Field(default=None, description="Bloc of the speaker")

    # Temporal information
    start_time: float | None = Field(default=None, description="Start time in seconds")
    end_time: float | None = Field(default=None, description="End time in seconds")
    duration: float | None = Field(default=None, description="Duration in seconds")

    # Sentiment and emotional analysis
    sentiment: SentimentCategory | None = Field(
        default=None, description="Sentiment classification"
    )
    sentiment_score: float | None = Field(
        default=None, ge=-1.0, le=1.0, description="Sentiment score from -1 to 1"
    )
    negation_aware_diplo: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Negation-aware DIPLO sentiment score",
    )
    tension_level: TensionLevel | None = Field(
        default=None, description="Tension level in the sentence"
    )

    # Linguistic features
    negation_type: NegationType | None = Field(
        default=None, description="Type of negation if present"
    )
    negation_cues: Sequence[NegationCue] = Field(
        default_factory=tuple, description="List of negation cues in this sentence"
    )
    hedging_type: HedgeType | None = Field(
        default=None, description="Type of hedging language used"
    )
    hedging_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Hedging score from 0 to 1"
    )
    politeness_act: PolitenessAct | None = Field(
        default=None, description="Politeness classification"
    )
    politeness_ratio: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Politeness ratio"
    )
    diplomatic_tone: DiplomaticTone | None = Field(
        default=None, description="Diplomatic tone classification"
    )
    appraisal_attitude: AppraisalAttitude | None = Field(
        default=None, description="Appraisal attitude"
    )

    # Topic analysis
    dominant_topic: TopicCategory | None = Field(
        default=None, description="Dominant topic category"
    )
    topic_specificity: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Topic specificity score"
    )
    topic_scores: dict[str, float] | None = Field(
        default=None, description="Topic scores for each category"
    )

    # Framing analysis
    dominant_frame: FrameType | None = Field(
        default=None, description="Dominant frame type"
    )
    evidence_types: list[EvidenceType] | None = Field(
        default=None, description="Evidence types used"
    )
    audience_type: AudienceType | None = Field(
        default=None, description="Target audience type"
    )

    # Face work analysis
    face_threat_count: int | None = Field(
        default=None, ge=0, description="Number of face-threatening acts"
    )
    face_save_count: int | None = Field(
        default=None, ge=0, description="Number of face-saving acts"
    )

    # Risk and Manipulation
    risk_score: float | None = Field(
        default=None, ge=0.0, le=10.0, description="Risk score"
    )
    manipulation_score: float | None = Field(
        default=None, le=1.0, description="Manipulation score"
    )
    is_demand: bool = Field(
        default=False, description="Whether the sentence contains a demand"
    )
    consensus_result: Any | None = Field(
        default=None, description="DualGateConsensusLayer sonucu"
    )
    speech_act: SpeechActClassification | None = Field(
        default=None, description="Speech act classification of the sentence"
    )

    # AI and Logic analysis results
    ai_analyzed: int = Field(
        default=0, description="Whether the sentence has been analyzed by AI"
    )
    logic_result: str | None = Field(
        default=None, description="Logic check validation result"
    )
    formula_inconsistency_score: float = Field(
        default=0.0, description="Formula inconsistency score"
    )
    discrepancy_score: float = Field(
        default=0.0, description="Discrepancy score between AI and formula"
    )
    entities_gpe: list[str] | None = Field(
        default=None, description="GPE entities in the sentence"
    )
    global_sent_order: int | None = Field(
        default=None, description="Global order of the sentence in the transcript"
    )

    # Metadata
    word_count: int | None = Field(
        default=None, ge=0, description="Number of words in the sentence"
    )
    confidence_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence score of analysis"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )

    srl_frames: list[SRLFrame] = Field(
        default_factory=list,
        description="PropBank semantic role labeling frames extracted from this sentence",
    )
    srl_extraction_status: ExtractionStatus = Field(
        default=ExtractionStatus.PENDING,
        description="SRL processing status for this sentence",
    )

    @property
    def has_negation(self) -> bool:
        """Checks if the sentence contains any negation cues."""
        return len(self.negation_cues) > 0

    @property
    def negation_count(self) -> int:
        """Returns the number of negation cues in the sentence."""
        return len(self.negation_cues)

    @property
    def has_srl_data(self) -> bool:
        """Check if SRL extraction completed successfully."""
        return (
            self.srl_extraction_status == ExtractionStatus.COMPLETED
            and len(self.srl_frames) > 0
        )

    @property
    def primary_action_triplets(self) -> list[tuple[str, str, str]]:
        """Get all complete triplets from this sentence's frames."""
        triplets = [f.to_triplet() for f in self.srl_frames if f.has_complete_triplet]
        return [t for t in triplets if t is not None]
