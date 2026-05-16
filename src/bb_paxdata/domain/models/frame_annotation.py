# src/bb_paxdata/domain/models/frame_annotation.py
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bb_paxdata.domain.enums.frame_type import FrameType


class FrameAnnotation(BaseModel):
    """Bir segment içindeki tek frame annotation'ı. Immutable.

    [Academic Ref: Entman, R.M. (1993). Framing: Toward Clarification of a Fractured Paradigm.]
    """

    model_config = ConfigDict(frozen=True)

    id: str
    frame_type: FrameType
    confidence: float = Field(ge=0.0, le=1.0)
    embedding_vector: list[float] | None = None
    matched_concepts: list[str] = Field(default_factory=list)
    keyword_weight: float = Field(default=1.0, ge=0.0)
    sentence_index: int = Field(ge=0)
    cue_source: Literal[
        "hamborg_embedding", "elassady_lexicon", "entman_cue", "syntactic_pattern"
    ] = "entman_cue"


class ResolvedEntity(BaseModel):
    """Coreference resolution sonucu. Immutable.

    [Academic Ref: Hamborg, F. (2023). NLP Techniques for Automated Frame Analysis.]
    """

    model_config = ConfigDict(frozen=True)

    text: str
    start_idx: int
    end_idx: int
    label: str
    main_reference: str | None = None
    actor_id: str | None = None
    embedding: list[float] | None = None


class FiveWOneH(BaseModel):
    """5W1H çıkarım sonucu. Immutable.

    [Academic Ref: Hamborg, F. (2023). NLP Techniques for Automated Frame Analysis. Who, What, When, Where, Why, How.]
    """

    model_config = ConfigDict(frozen=True)

    who: list[str] = Field(default_factory=list)
    what: list[str] = Field(default_factory=list)
    when: list[str] = Field(default_factory=list)
    where: list[str] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)
    how: list[str] = Field(default_factory=list)


class PerspectiveCluster(BaseModel):
    """Perspektif kümeleme sonucu. Immutable.

    [Academic Ref: Hamborg, F. (2023). Perspective clustering — identifying actor-based viewpoints.]
    """

    model_config = ConfigDict(frozen=True)

    actor_id: str
    entities: list[ResolvedEntity]
    embedding_centroid: list[float] | None = None


class BiasSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BiasSignal(BaseModel):
    """Bias tespiti sinyali. Immutable.

    [Academic Ref: Hamborg, F. (2023). Bias detection via cosine similarity thresholding.]
    """

    model_config = ConfigDict(frozen=True)

    frame_annotation_id: str
    cosine_distance: float
    threshold: float
    severity: BiasSeverity


class FrameDetectionResult(BaseModel):
    """Hamborg (2023) PFA pipeline tam sonucu. Immutable."""

    model_config = ConfigDict(frozen=True)

    segment_id: str
    concepts: list[str]
    resolved_entities: list[ResolvedEntity]
    frame_annotations: list[FrameAnnotation]
    perspectives: list[PerspectiveCluster]
    five_w_one_h: FiveWOneH
    bias_signals: list[BiasSignal]
    prompt_version: str
    prompt_sha256: str


class FrameSalienceResult(BaseModel):
    """Entman (1993) frame salience hesaplama sonucu. Immutable.

    [Academic Ref: Entman, R.M. (1993). Framing: Toward Clarification of a Fractured Paradigm.]
    """

    model_config = ConfigDict(frozen=True)

    segment_id: str
    salience_scores: dict[FrameType, float] = Field(
        description="Her frame tipi için Entman (1993) salience skoru"
    )
    dominant_frame: FrameType | None = Field(
        description="argmax_k(FrameSalience_k) — baskın çerçeve"
    )
    is_competitive: bool = Field(
        description="Chong & Druckman (2007) rekabetçi frame durumu"
    )
    competing_frames: list[FrameType] = Field(
        default_factory=list, description="Rekabet halindeki frame'ler"
    )

    @property
    def effective_dominant(self) -> FrameType:
        """None-safe dominant frame erişimi."""
        if self.dominant_frame is None:
            return FrameType.PROBLEM_DEFINITION  # Default fallback
        return self.dominant_frame


class CueMatch(BaseModel):
    """Lexicon match result for El-Assady (2023) cues."""

    model_config = ConfigDict(frozen=True)

    token_text: str
    token_idx: int
    cue_category: str
    frame_hint: FrameType | None
    pos_tag: str
    dependency: str
    weight: float
