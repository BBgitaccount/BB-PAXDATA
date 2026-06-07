"""
Language detection service for BB-PAXDATA.

Wraps `langdetect` with:
- Deterministic seeding for reproducibility
- Script-based fallback for Arabic (Unicode U+0600–U+06FF)
  and Cyrillic (U+0400–U+04FF)
- Safe exception handling (always returns a valid language code)

Supported output codes:
    "tr"  → Turkish   (tr_core_news_trf SpaCy model)
    "en"  → English   (en_core_web_trf SpaCy model)
    "ar"  → Arabic    (no SpaCy model yet; regex fallback)
    "ru"  → Russian / Cyrillic (no SpaCy model yet; regex fallback)
"""

import re

from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import (
    LangDetectException,
)

# Seed langdetect for deterministic results across runs.
# Must be set once at import time.
DetectorFactory.seed = 0


class LanguageDetector:
    """
    Detect the primary language of a diplomatic transcript text.

    The detection pipeline:
    1. Attempt `langdetect.detect()` for ISO 639-1 code.
    2. If the detected language is in SUPPORTED_LANGS, return it.
    3. If not supported, try Unicode script detection (Arabic/Cyrillic).
    4. Fallback to FALLBACK_LANG ("en") for any error or unknown script.

    Usage::

        lang = LanguageDetector.detect("Türkiye diyalogu desteklemektedir.")
        # Returns: "tr"
    """

    SUPPORTED_LANGS: frozenset[str] = frozenset({"tr", "en"})
    FALLBACK_LANG: str = "en"

    # Regex patterns for script-based detection
    _ARABIC_PATTERN: re.Pattern[str] = re.compile(r"[\u0600-\u06ff]")
    _CYRILLIC_PATTERN: re.Pattern[str] = re.compile(r"[\u0400-\u04ff]")

    @classmethod
    def detect(cls, text: str) -> str:
        """
        Detect the primary language of the given text.

        Args:
            text: Plain text to analyze. Should be at least a sentence
                  for reliable detection (langdetect needs ~20+ chars).

        Returns:
            ISO 639-1 language code string: one of "tr", "en", "ar", "ru",
            or FALLBACK_LANG ("en") if detection fails.
        """
        if not text or not text.strip():
            return cls.FALLBACK_LANG

        try:
            lang: str = detect(text)

            if lang in cls.SUPPORTED_LANGS:
                return lang

            # Unsupported language: try script-based detection
            if cls._is_arabic_script(text):
                return "ar"
            if cls._is_cyrillic_script(text):
                return "ru"

            # Langdetect returned a code we don't model yet
            return cls.FALLBACK_LANG

        except LangDetectException:
            # Very short text or character noise → safe fallback
            return cls.FALLBACK_LANG

    @classmethod
    def _is_arabic_script(cls, text: str) -> bool:
        """Return True if text contains Arabic-script characters."""
        return bool(cls._ARABIC_PATTERN.search(text))

    @classmethod
    def _is_cyrillic_script(cls, text: str) -> bool:
        """Return True if text contains Cyrillic-script characters."""
        return bool(cls._CYRILLIC_PATTERN.search(text))
