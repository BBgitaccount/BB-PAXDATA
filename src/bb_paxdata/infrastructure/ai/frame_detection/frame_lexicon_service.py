# src/bb_paxdata/infrastructure/ai/frame_detection/frame_lexicon_service.py
"""El-Assady (2023) frame lexicon and cue detection service.

[Academic Reference: El-Assady, M. et al. (2023). Towards a More In-Depth Detection 
of Political Framing. ACL Anthology. Discourse connectives, modal particles, 
POS/dependency feature set for fine-grained frame detection.]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from spacy.language import Language

import asyncio

import structlog
from bb_paxdata.domain.enums.frame_type import FrameType
from bb_paxdata.domain.models.frame_annotation import CueMatch
from spacy.tokens import Doc, Token

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# El-Assady (2023) Uzman-Curated Cue Listesi
# ---------------------------------------------------------------------------

EL_ASSADY_CUE_LEXICON: Final[dict[str, dict[Any, list[str]]]] = {
    "discourse_connectives": {
        "cause": ["because", "since", "therefore", "thus", "consequently", "hence"],
        "contrast": [
            "however",
            "although",
            "nevertheless",
            "yet",
            "but",
            "despite",
            "conversely",
        ],
        "additive": [
            "furthermore",
            "moreover",
            "in addition",
            "also",
            "besides",
            "likewise",
        ],
        "temporal": [
            "before",
            "after",
            "meanwhile",
            "subsequently",
            "then",
            "previously",
            "during",
        ],
    },
    "modal_particles": {
        "epistemic": [
            "possibly",
            "perhaps",
            "certainly",
            "definitely",
            "allegedly",
            "reportedly",
        ],
        "deontic": ["must", "should", "ought", "required", "necessary", "obligatory"],
        "dynamic": ["can", "could", "may", "might", "able", "capable"],
    },
    "framing_cues": {
        FrameType.PROBLEM_DEFINITION: [
            "crisis",
            "threat",
            "challenge",
            "issue",
            "problem",
            "danger",
            "risk",
            "urgent",
        ],
        FrameType.CAUSE_INTERPRETATION: [
            "cause",
            "reason",
            "source",
            "origin",
            "trigger",
            "lead",
            "result",
        ],
        FrameType.MORAL_EVALUATION: [
            "unacceptable",
            "unjust",
            "fair",
            "right",
            "wrong",
            "accountable",
            "blame",
            "duty",
        ],
        FrameType.REMEDY_SUGGESTION: [
            "solution",
            "resolve",
            "address",
            "tackle",
            "handle",
            "fix",
            "remedy",
            "measure",
        ],
    },
}


class FrameLexiconService:
    """El-Assady (2023) discourse connective ve framing cue detection servisi.

    Hybrid yaklaşım:
    1. Rule-based: Önceden tanımlı cue listesi + POS/dependency pattern matching
    2. Neural: spaCy dependency parse üzerinden yapısal pattern tespiti
    """

    def __init__(self, nlp: Language) -> None:
        self._nlp = nlp
        self._cue_lexicon = EL_ASSADY_CUE_LEXICON
        self._log = logger.bind(service="frame_lexicon")

    async def detect_cues(self, segment_text: str) -> list[CueMatch]:
        """Metindeki discourse connective ve framing cue'larını tespit et."""
        doc: Doc = await asyncio.to_thread(self._nlp, segment_text)
        matches: list[CueMatch] = []

        for token in doc:
            token_lower = token.lower_

            # 1. Discourse connective check
            for category, cues in self._cue_lexicon["discourse_connectives"].items():
                if token_lower in cues:
                    frame_hint = self._map_connective_to_frame(category)
                    matches.append(
                        CueMatch(
                            token_text=token.text,
                            token_idx=token.i,
                            cue_category=f"connective_{category}",
                            frame_hint=frame_hint,
                            pos_tag=token.pos_,
                            dependency=token.dep_,
                            weight=self._compute_connective_weight(token, category),
                        )
                    )

            # 2. Modal particle check
            for category, cues in self._cue_lexicon["modal_particles"].items():
                if token_lower in cues:
                    frame_hint = self._map_modal_to_frame(category)
                    matches.append(
                        CueMatch(
                            token_text=token.text,
                            token_idx=token.i,
                            cue_category=f"modal_{category}",
                            frame_hint=frame_hint,
                            pos_tag=token.pos_,
                            dependency=token.dep_,
                            weight=self._compute_modal_weight(token, category),
                        )
                    )

            # 3. Framing cue check (Entman 1993 lexical cues)
            for frame_type, cues in self._cue_lexicon["framing_cues"].items():
                if token_lower in cues:
                    matches.append(
                        CueMatch(
                            token_text=token.text,
                            token_idx=token.i,
                            cue_category=f"frame_{frame_type!s}",
                            frame_hint=frame_type,
                            pos_tag=token.pos_,
                            dependency=token.dep_,
                            weight=self._compute_framing_weight(token, frame_type),
                        )
                    )

            # 4. Syntactic pattern check (El-Assady 2023 dependency features)
            syntactic_match = self._check_syntactic_pattern(token)
            if syntactic_match:
                matches.append(syntactic_match)

        self._log.debug("cues_detected", count=len(matches))
        return matches

    def _map_connective_to_frame(self, category: str) -> FrameType | None:
        """Discourse connective kategorisini Entman frame'ine eşle."""
        mapping = {
            "cause": FrameType.CAUSE_INTERPRETATION,
            "contrast": FrameType.PROBLEM_DEFINITION,
            "additive": FrameType.PROBLEM_DEFINITION,
            "temporal": None,
        }
        return mapping.get(category)

    def _map_modal_to_frame(self, category: str) -> FrameType | None:
        """Modal particle kategorisini Entman frame'ine eşle."""
        mapping = {
            "epistemic": None,
            "deontic": FrameType.MORAL_EVALUATION,
            "dynamic": FrameType.REMEDY_SUGGESTION,
        }
        return mapping.get(category)

    def _compute_connective_weight(self, token: Token, category: str) -> float:
        base = 1.0
        if token.is_sent_start:
            base *= 1.5
        if category == "cause":
            base *= 1.2
        return base

    def _compute_modal_weight(self, token: Token, category: str) -> float:
        weights = {"epistemic": 1.0, "deontic": 1.3, "dynamic": 1.1}
        return weights.get(category, 1.0)

    def _compute_framing_weight(self, token: Token, frame_type: FrameType) -> float:
        base_weights = {
            FrameType.PROBLEM_DEFINITION: 1.0,
            FrameType.CAUSE_INTERPRETATION: 1.1,
            FrameType.MORAL_EVALUATION: 1.2,
            FrameType.REMEDY_SUGGESTION: 1.0,
        }
        return base_weights.get(frame_type, 1.0)

    def _check_syntactic_pattern(self, token: Token) -> CueMatch | None:
        """Dependency parse üzerinden El-Assady (2023) pattern matching."""
        if token.dep_ == "ROOT" and token.pos_ == "VERB":
            has_nsubj = any(child.dep_ == "nsubj" for child in token.children)
            has_dobj = any(child.dep_ == "dobj" for child in token.children)
            if has_nsubj and has_dobj:
                return CueMatch(
                    token_text=token.text,
                    token_idx=token.i,
                    cue_category="syntactic_nsubj_root_dobj",
                    frame_hint=FrameType.PROBLEM_DEFINITION,
                    pos_tag=token.pos_,
                    dependency=token.dep_,
                    weight=1.4,
                )
        return None
