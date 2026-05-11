from datetime import datetime

from pydantic import BaseModel, Field

from ..enums import (
    AppraisalAttitude,
    AudienceType,
    DiplomaticTone,
    EvidenceType,
    FrameType,
    HedgingType,
    NegationType,
    PolitenessAct,
    SentimentCategory,
    TensionLevel,
    TopicCategory,
)


class Sentence(BaseModel):
    """Represents a single sentence in a transcript with analysis metadata."""

    id: str = Field(..., description="Unique identifier for the sentence")
    text: str = Field(..., description="The actual text content of the sentence")
    speaker_id: str | None = Field(
        None, description="ID of the speaker who uttered this sentence"
    )
    segment_id: str | None = Field(
        None, description="ID of the segment this sentence belongs to"
    )

    # Temporal information
    start_time: float | None = Field(None, description="Start time in seconds")
    end_time: float | None = Field(None, description="End time in seconds")
    duration: float | None = Field(None, description="Duration in seconds")

    # Sentiment and emotional analysis
    sentiment: SentimentCategory | None = Field(
        None, description="Sentiment classification"
    )
    sentiment_score: float | None = Field(
        None, ge=-1.0, le=1.0, description="Sentiment score from -1 to 1"
    )
    negation_aware_diplo: float | None = Field(
        None, ge=-1.0, le=1.0, description="Negation-aware DIPLO sentiment score"
    )
    tension_level: TensionLevel | None = Field(
        None, description="Tension level in the sentence"
    )

    # Linguistic features
    negation_type: NegationType | None = Field(
        None, description="Type of negation if present"
    )
    hedging_type: HedgingType | None = Field(
        None, description="Type of hedging language used"
    )
    hedging_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Hedging score from 0 to 1"
    )
    politeness_act: PolitenessAct | None = Field(
        None, description="Politeness classification"
    )
    politeness_ratio: float | None = Field(
        None, ge=0.0, le=1.0, description="Politeness ratio"
    )
    diplomatic_tone: DiplomaticTone | None = Field(
        None, description="Diplomatic tone classification"
    )
    appraisal_attitude: AppraisalAttitude | None = Field(
        None, description="Appraisal attitude"
    )

    # Topic analysis
    dominant_topic: TopicCategory | None = Field(
        None, description="Dominant topic category"
    )
    topic_specificity: float | None = Field(
        None, ge=0.0, le=1.0, description="Topic specificity score"
    )
    topic_scores: dict[str, float] | None = Field(
        None, description="Topic scores for each category"
    )

    # Framing analysis
    dominant_frame: FrameType | None = Field(None, description="Dominant frame type")
    evidence_types: list[EvidenceType] | None = Field(
        None, description="Evidence types used"
    )
    audience_type: AudienceType | None = Field(None, description="Target audience type")

    # Face work analysis
    face_threat_count: int | None = Field(
        None, ge=0, description="Number of face-threatening acts"
    )
    face_save_count: int | None = Field(
        None, ge=0, description="Number of face-saving acts"
    )

    # Risk and Manipulation
    risk_score: float | None = Field(None, ge=0.0, le=10.0, description="Risk score")
    manipulation_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Manipulation score"
    )
    is_demand: bool = Field(False, description="Whether the sentence contains a demand")

    # Metadata
    word_count: int | None = Field(
        None, ge=0, description="Number of words in the sentence"
    )
    confidence_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence score of analysis"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
