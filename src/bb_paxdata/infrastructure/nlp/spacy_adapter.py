from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.language import Language

from spacy.tokens import Doc

from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.nlp.negation_detector import SpacyNegationDetector


class SpacyAdapter:
    """Adapter for orchestrating spaCy NLP tasks including negation detection."""

    def __init__(self, nlp: Language) -> None:
        self._nlp = nlp
        self._negation_detector = SpacyNegationDetector(nlp)

    async def analyze_sentence(self, text: str, sentence_id: str) -> Sentence:
        """Analyze a sentence and return a Sentence model with negation cues."""
        doc: Doc = self._nlp(text)

        # Phase 2: Negation detection on the same Doc
        negation_cues = await self._negation_detector.detect_with_doc(
            text, sentence_id, doc
        )

        # Create Sentence model (base fields, negation will be populated)
        # Note: In a real implementation, other fields like entities, sentiment would be here too.
        # This implementation focuses on the Negation integration as requested.
        return Sentence(
            id=sentence_id,
            text=text,
            negation_cues=negation_cues,
            word_count=len(doc),
        )
