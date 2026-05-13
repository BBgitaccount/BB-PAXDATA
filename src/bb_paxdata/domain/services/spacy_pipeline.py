"""
SpaCy Pipeline Service for BB-PAXDATA.

Provides high-level wrappers for processing text and batches using SpaCy.
"""

from collections.abc import Iterable

from spacy.tokens import Doc

from bb_paxdata.infrastructure.nlp.spacy_manager import SpacyModelManager


class SpacyPipeline:
    """
    Service wrapper for SpaCy processing.
    """

    @staticmethod
    def process_text(text: str, lang: str) -> Doc:
        """
        Process a single text string.

        Args:
            text: The text to process.
            lang: Language code for model selection.

        Returns:
            A SpaCy Doc object.
        """
        nlp = SpacyModelManager.get_model(lang)
        return nlp(text)

    @staticmethod
    def process_batch(
        texts: Iterable[str], lang: str, batch_size: int = 50
    ) -> list[Doc]:
        """
        Process a batch of texts efficiently using nlp.pipe().

        Args:
            texts: An iterable of text strings.
            lang: Language code for model selection.
            batch_size: Number of texts to process per batch.

        Returns:
            A list of SpaCy Doc objects.
        """
        nlp = SpacyModelManager.get_model(lang)
        return list(nlp.pipe(texts, batch_size=batch_size))
