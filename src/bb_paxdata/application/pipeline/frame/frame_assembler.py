# src/bb_paxdata/application/pipeline/frame/frame_assembler.py
"""Entman (1993) FrameSalience calculation and assembly.

[Academic Reference: Entman, R.M. (1993). Framing: Toward Clarification of a Fractured 
Paradigm. Journal of Communication, 43(4), 51–58. 
FrameSalience_k = Σ(KeywordWeight_i × PositionBoost_i) / SegmentLength]
"""

import asyncio
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from spacy.language import Language

import structlog
from bb_paxdata.domain.enums.frame_type import FrameType
from bb_paxdata.domain.models.frame_annotation import (
    CueMatch,
    FrameAnnotation,
    FrameSalienceResult,
)
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.infrastructure.ai.frame_detection.frame_lexicon_service import (
    FrameLexiconService,
)
from spacy.tokens import Doc

logger = structlog.get_logger(__name__)

# Entman (1993) position boost constants
POSITION_BOOST_PRIMACY: Final[float] = 1.5  # First 20%
POSITION_BOOST_RECENCY: Final[float] = 1.3  # Last 20%
POSITION_BOOST_MIDDLE: Final[float] = 1.0  # Middle 60%

# Chong & Druckman (2007) competitive frame threshold
FRAME_COMPETITION_THRESHOLD: Final[float] = 0.15


class FrameAssembler:
    """Entman (1993) FrameSalience formülünün implementasyonu."""

    def __init__(
        self,
        lexicon_service: FrameLexiconService,
        nlp: Language,
    ) -> None:
        self._lexicon = lexicon_service
        self._nlp = nlp
        self._log = logger.bind(assembler="frame")

    async def assemble_frame_salience(
        self,
        segment: Segment,
        annotations: list[FrameAnnotation],
        cues: list[CueMatch],
    ) -> FrameSalienceResult:
        """Segment için tüm frame salience skorlarını hesapla."""
        # Note: We need tokens to calculate length. If segment.tokens is empty,
        # we might need to tokenize or use text length.
        # Assuming Segment has tokens or we can use the doc length.
        doc: Doc = await asyncio.to_thread(self._nlp, segment.text)
        doc_length = len(doc)

        if doc_length == 0:
            return FrameSalienceResult(
                segment_id=segment.id,
                salience_scores={},
                dominant_frame=None,
                is_competitive=False,
                competing_frames=[],
            )

        frame_types = [
            FrameType.PROBLEM_DEFINITION,
            FrameType.CAUSE_INTERPRETATION,
            FrameType.MORAL_EVALUATION,
            FrameType.REMEDY_SUGGESTION,
        ]
        salience_scores: dict[FrameType, float] = {}

        for frame_type in frame_types:
            score = self._compute_frame_salience(doc, annotations, cues, frame_type)
            salience_scores[frame_type] = score

        dominant = self._determine_dominant_frame(salience_scores)
        is_competitive, competing = self._analyze_frame_competition(salience_scores)

        return FrameSalienceResult(
            segment_id=segment.id,
            salience_scores=salience_scores,
            dominant_frame=dominant,
            is_competitive=is_competitive,
            competing_frames=competing,
        )

    def _compute_frame_salience(
        self,
        doc: Doc,
        annotations: list[FrameAnnotation],
        cues: list[CueMatch],
        frame_type: FrameType,
    ) -> float:
        """Tek bir frame tipi için Entman (1993) salience skorunu hesapla."""
        total_weighted_score = 0.0
        doc_length = len(doc)

        # 1. El-Assady cues
        for cue in cues:
            if cue.frame_hint == frame_type:
                boost = self._position_boost(cue.token_idx, doc_length)
                total_weighted_score += cue.weight * boost

        # 2. Hamborg annotations
        for ann in annotations:
            if ann.frame_type == frame_type:
                # Assuming sentence_index is available
                # Map sentence_index to a relative position in doc tokens
                # This is an approximation
                num_sents = len(list(doc.sents))
                relative_pos = ann.sentence_index / num_sents if num_sents > 0 else 0
                boost = self._position_boost(int(relative_pos * doc_length), doc_length)
                total_weighted_score += ann.keyword_weight * boost

        return total_weighted_score / doc_length if doc_length > 0 else 0.0

    def _position_boost(self, position: int, total_length: int) -> float:
        if total_length == 0:
            return POSITION_BOOST_MIDDLE
        relative = position / total_length
        if relative < 0.2:
            return POSITION_BOOST_PRIMACY
        elif relative > 0.8:
            return POSITION_BOOST_RECENCY
        return POSITION_BOOST_MIDDLE

    def _determine_dominant_frame(
        self, scores: dict[FrameType, float]
    ) -> FrameType | None:
        valid_scores = {k: v for k, v in scores.items() if v > 0}
        if not valid_scores:
            return None
        return max(valid_scores, key=lambda k: valid_scores[k])

    def _analyze_frame_competition(
        self, scores: dict[FrameType, float]
    ) -> tuple[bool, list[FrameType]]:
        sorted_frames = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_frames) < 2:
            return False, []

        top_score = sorted_frames[0][1]
        second_score = sorted_frames[1][1]
        diff = top_score - second_score
        is_competitive = diff < FRAME_COMPETITION_THRESHOLD and second_score > 0.05

        competing = []
        if is_competitive:
            competing = [
                ft
                for ft, sc in sorted_frames
                if abs(sc - top_score) < FRAME_COMPETITION_THRESHOLD and sc > 0.05
            ]
        return is_competitive, competing
