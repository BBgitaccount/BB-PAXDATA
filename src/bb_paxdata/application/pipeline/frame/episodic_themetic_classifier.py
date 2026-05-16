# src/bb_paxdata/application/pipeline/frame/episodic_themetic_classifier.py
"""Iyengar (1991) Episodic vs Thematic framing classifier.

[Academic Reference: Iyengar, S. (1991). Is Anyone Responsible? How Television Frames 
Political Issues. Episodic (individual/event-focused) vs Thematic (structural/context-focused) 
frame distinction.]
"""

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from spacy.language import Language

import structlog
from bb_paxdata.domain.enums.frame_type import FrameType
from bb_paxdata.domain.models.segment import Segment
from spacy.tokens import Doc

logger = structlog.get_logger(__name__)

# Iyengar (1991) Episodic/Thematic lexical markers
EPISODIC_MARKERS: Final[set[str]] = {
    "yesterday",
    "today",
    "recently",
    "incident",
    "event",
    "attack",
    "meeting",
    "summit",
    "conference",
    "happened",
    "occurred",
}

THEMATIC_MARKERS: Final[set[str]] = {
    "systemic",
    "structural",
    "chronic",
    "persistent",
    "ongoing",
    "long-term",
    "trend",
    "pattern",
    "historically",
    "generally",
    "widespread",
    "pervasive",
}

ABSTRACT_NOUNS: Final[set[str]] = {
    "peace",
    "security",
    "stability",
    "democracy",
    "sovereignty",
    "prosperity",
    "justice",
    "equality",
    "freedom",
    "diplomacy",
    "bilateralism",
}


@dataclass(frozen=True)
class EpisodicThematicFeatures:
    """Iyengar (1991) distinctive feature vector."""

    ner_density: float
    temporal_count: int
    episodic_marker_count: int
    thematic_marker_count: int
    abstract_noun_ratio: float
    named_actor_count: int
    generalization_ratio: float
    action_verb_ratio: float

    @property
    def episodic_score(self) -> float:
        score = (
            self.ner_density * 2.0
            + min(self.temporal_count, 5) * 0.3
            + self.episodic_marker_count * 0.4
            + self.named_actor_count * 0.5
            - self.abstract_noun_ratio * 1.0
            - self.thematic_marker_count * 0.3
            - self.generalization_ratio * 1.5
        )
        return max(0.0, score)

    @property
    def thematic_score(self) -> float:
        score = (
            self.abstract_noun_ratio * 2.0
            + self.thematic_marker_count * 0.5
            + self.generalization_ratio * 1.5
            - self.ner_density * 1.0
            - self.temporal_count * 0.2
            - self.episodic_marker_count * 0.3
            - self.named_actor_count * 0.4
        )
        return max(0.0, score)


class EpisodicThematicClassifier:
    """Iyengar (1991) Episodic vs Thematic framing sınıflandırıcısı."""

    def __init__(self, nlp: Language) -> None:
        self._nlp = nlp
        self._log = logger.bind(classifier="episodic_themetic")

    async def classify(self, segment: Segment) -> FrameType:
        """Segment'i Episodic veya Thematic olarak sınıflandır."""
        if not segment.text or not segment.text.strip():
            raise ValueError("Segment text cannot be empty")

        doc: Doc = await asyncio.to_thread(self._nlp, segment.text)
        features = self._extract_features(doc)

        if features.episodic_score > features.thematic_score:
            return FrameType.EPISODIC
        return FrameType.THEMATIC

    def _extract_features(self, doc: Doc) -> EpisodicThematicFeatures:
        total_tokens = len(doc)
        if total_tokens == 0:
            return EpisodicThematicFeatures(0, 0, 0, 0, 0.0, 0, 0.0, 0.0)

        entities = list(doc.ents)
        ner_density = len(entities) / total_tokens
        temporal_count = sum(1 for e in entities if e.label_ in ("DATE", "TIME"))
        named_actor_count = sum(
            1 for e in entities if e.label_ in ("GPE", "ORG", "PERSON")
        )

        tokens_lower = [t.lower_ for t in doc]
        episodic_count = sum(1 for t in tokens_lower if t in EPISODIC_MARKERS)
        thematic_count = sum(1 for t in tokens_lower if t in THEMATIC_MARKERS)

        nouns = [t for t in doc if t.pos_ == "NOUN"]
        abstract_count = sum(1 for t in nouns if t.lower_ in ABSTRACT_NOUNS)
        abstract_ratio = abstract_count / len(nouns) if nouns else 0.0

        gen_markers = {"always", "never", "generally", "typically", "all", "every"}
        gen_count = sum(1 for t in tokens_lower if t in gen_markers)
        num_sents = len(list(doc.sents))
        gen_ratio = gen_count / num_sents if num_sents > 0 else 0.0

        verbs = [t for t in doc if t.pos_ == "VERB"]
        action_verbs = {"signed", "met", "agreed", "refused", "attacked", "visited"}
        action_count = sum(1 for t in verbs if t.lemma_.lower() in action_verbs)
        action_ratio = action_count / len(verbs) if verbs else 0.0

        return EpisodicThematicFeatures(
            ner_density=ner_density,
            temporal_count=temporal_count,
            episodic_marker_count=episodic_count,
            thematic_marker_count=thematic_count,
            abstract_noun_ratio=abstract_ratio,
            named_actor_count=named_actor_count,
            generalization_ratio=gen_ratio,
            action_verb_ratio=action_ratio,
        )
