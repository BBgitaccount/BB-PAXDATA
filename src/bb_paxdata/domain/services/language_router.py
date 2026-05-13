"""
Language Router for BB-PAXDATA.

Maps ISO 639-1 language codes to the appropriate NLP configuration:
- SpaCy model name
- Sentiment lexicon name
- Negation word set name
- Stopword set name

This router is the single source of truth for which resources
to load for a given language. Adding a new language requires
only adding an entry to ROUTES.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageConfig:
    """
    NLP configuration bundle for a specific language.

    Attributes:
        spacy_model: Name of the SpaCy model to load.
        sentiment_lexicon: Key of the sentiment lexicon to use.
        negation_words: Key of the negation word set.
        stopwords: Key of the stopword set.
    """

    spacy_model: str
    sentiment_lexicon: str
    negation_words: str
    stopwords: str


class LanguageRouter:
    """
    Route a language code to the appropriate NLP resource configuration.

    Usage::

        config = LanguageRouter.get_config("tr")
        # config.spacy_model → "tr_core_news_trf"
        # config.sentiment_lexicon → "DIPLO_LEXICON_TR"

        # Unknown / unsupported language falls back to English:
        config = LanguageRouter.get_config("zh")
        # config.spacy_model → "en_core_web_trf"
    """

    ROUTES: dict[str, LanguageConfig] = {
        "tr": LanguageConfig(
            spacy_model="tr_core_news_trf",
            sentiment_lexicon="DIPLO_LEXICON_TR",
            negation_words="NEGATION_WORDS_TR",
            stopwords="STOPWORDS_TR",
        ),
        "en": LanguageConfig(
            spacy_model="en_core_web_trf",
            sentiment_lexicon="DIPLO_LEXICON",
            negation_words="NEGATION_WORDS",
            stopwords="STOPWORDS",
        ),
    }

    # Default configuration used when a language has no entry in ROUTES
    _DEFAULT_LANG: str = "en"

    @classmethod
    def get_config(cls, lang: str) -> LanguageConfig:
        """
        Return the NLP configuration for the given language code.

        Args:
            lang: ISO 639-1 language code (e.g. "tr", "en", "ar").

        Returns:
            LanguageConfig for the language, or the English fallback
            if the language is unsupported.
        """
        return cls.ROUTES.get(lang, cls.ROUTES[cls._DEFAULT_LANG])

    @classmethod
    def supported_languages(cls) -> list[str]:
        """Return list of language codes with dedicated SpaCy models."""
        return list(cls.ROUTES.keys())

    @classmethod
    def has_spacy_model(cls, lang: str) -> bool:
        """Return True if the language has a dedicated SpaCy model configured."""
        return lang in cls.ROUTES
