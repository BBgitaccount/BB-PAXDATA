from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.language import Language

from spacy.tokens import Doc

from bb_paxdata.application.domain.models.negation_cue import LanguageCode
from bb_paxdata.application.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.nlp.negation_detector import SpacyNegationDetector


class SpacyAdapter:
    """Adapter for orchestrating spaCy NLP tasks including negation detection."""

    def __init__(self, nlp: Language) -> None:
        self._nlp = nlp
        self._negation_detector = SpacyNegationDetector(nlp)

    async def analyze_sentence(self, text: str, sentence_id: str) -> Sentence:
        """Analyze a sentence and return a Sentence model with negation cues."""
        doc: Doc = self._nlp(text)

        # Resolve language from spaCy metadata
        lang_str = self._nlp.meta.get("lang", "en")
        language = LanguageCode.TR if lang_str == "tr" else LanguageCode.EN

        # Phase 2: Negation detection on the same Doc
        negation_result = await self._negation_detector.detect_with_doc(
            doc, sentence_id, language
        )

        # Create Sentence model (base fields, negation will be populated)
        # Note: In a real implementation, other fields like entities, sentiment would be here too.
        # This implementation focuses on the Negation integration as requested.
        return Sentence(
            id=sentence_id,
            text=text,
            negation_cues=negation_result.cues,
            word_count=len(doc),
        )
