"""
SpaCy Model Manager for BB-PAXDATA.

Handles lazy loading, caching, and unloading of SpaCy models to manage memory
efficiently. Implemented as a singleton-like class manager.
"""

import spacy

from .spacy_config import SPACY_PIPELINES


class SpacyModelManager:
    """
    Manager for SpaCy language models.

    Provides a central point to access pre-loaded models and handles
    unloading models when they are no longer needed.
    """

    _models: dict[str, spacy.Language] = {}

    @classmethod
    def get_model(cls, lang: str) -> spacy.Language:
        """
        Get a SpaCy model for the specified language.

        If the model is not already loaded, it will be loaded using the
        configuration from SPACY_PIPELINES.

        Args:
            lang: ISO 639-1 language code (e.g., 'tr', 'en').

        Returns:
            The loaded spacy.Language model.
        """
        if lang not in cls._models:
            if lang not in SPACY_PIPELINES:
                # Fallback to english if language not explicitly configured
                lang = "en"

            config = SPACY_PIPELINES[lang]
            cls._models[lang] = spacy.load(
                config["model"], disable=config.get("disabled", [])
            )
        return cls._models[lang]

    @classmethod
    def unload(cls, lang: str) -> None:
        """
        Unload a model from memory.

        Args:
            lang: ISO 639-1 language code to unload.
        """
        if lang in cls._models:
            del cls._models[lang]

    @classmethod
    def unload_all(cls) -> None:
        """Unload all loaded models to free up memory."""
        cls._models.clear()
