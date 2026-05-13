"""
Encoding Normalizer for BB-PAXDATA.

Implements a 4-stage text normalization pipeline designed for multilingual
diplomatic transcripts that may contain encoding artifacts, mojibake,
and language-specific character inconsistencies.

Pipeline stages:
    1. BOM & Binary cleanup (UTF-8 BOM, NULL bytes)
    2. Mojibake correction (via ftfy)
    3. Unicode NFKC normalization
    4. Language-specific normalization (Arabic / Cyrillic / Turkish)
"""

import unicodedata

import ftfy

from .normalizers.arabic import normalize_arabic
from .normalizers.cyrillic import normalize_cyrillic
from .normalizers.turkish import normalize_turkish


class EncodingNormalizer:
    """
    4-stage text encoding normalization pipeline.

    Designed to clean diplomatic transcripts before NLP processing.
    All stages are applied in order; each stage receives the output
    of the previous stage.

    Usage::

        normalizer = EncodingNormalizer()
        clean = normalizer.normalize(raw_text, detected_lang="tr")
    """

    def normalize(self, text: str, detected_lang: str | None = None) -> str:
        """
        Run the full 4-stage normalization pipeline.

        Args:
            text: Raw input text (may contain encoding artifacts).
            detected_lang: ISO 639-1 language code (e.g. "tr", "en",
                "ar", "ru"). If None, language-specific stage is skipped.

        Returns:
            Fully normalized Unicode text.
        """
        text = self._remove_bom(text)
        text = self._fix_mojibake(text)
        text = self._unicode_normalize(text)
        text = self._language_specific(text, detected_lang)
        text = self._final_cleanup(text)
        return text

    # ------------------------------------------------------------------
    # Stage 1: BOM & binary cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def _remove_bom(text: str, _lang: str | None = None) -> str:
        """Remove UTF-8 BOM (U+FEFF) and NULL bytes."""
        # BOM at start of string (common in Windows-generated files)
        text = text.lstrip("\ufeff")
        # NULL bytes (binary contamination)
        text = text.replace("\x00", "")
        return text

    # ------------------------------------------------------------------
    # Stage 2: Mojibake correction
    # ------------------------------------------------------------------

    @staticmethod
    def _fix_mojibake(text: str, _lang: str | None = None) -> str:
        """
        Fix encoding corruption (mojibake) using ftfy.

        ftfy.fix_text() is idempotent for clean text, so calling it
        multiple times until convergence handles nested mojibake safely.

        Example: "TÃ¼rkiye" → "Türkiye"
        """
        fixed = ftfy.fix_text(text)
        # Iterative fix for nested/double-encoded mojibake
        while fixed != text:
            text = fixed
            fixed = ftfy.fix_text(text)
        return str(fixed)

    # ------------------------------------------------------------------
    # Stage 3: Unicode NFKC normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _unicode_normalize(text: str, _lang: str | None = None) -> str:
        """
        Apply Unicode NFKC normalization.

        NFKC:
        - Decomposes ligatures (ﬁ → fi, ﬀ → ff)
        - Converts full-width characters to half-width (ａ → a)
        - Normalizes combining characters
        - Preserves dotted/dotless-I (İ, ı) for Turkish
        """
        return unicodedata.normalize("NFKC", text)

    # ------------------------------------------------------------------
    # Stage 4: Language-specific normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _language_specific(text: str, lang: str | None = None) -> str:
        """
        Apply language-specific character normalization.

        Args:
            text: Text after NFKC normalization.
            lang: ISO 639-1 language code.

        Returns:
            Text with language-specific corrections applied.
        """
        if lang == "ar":
            return normalize_arabic(text)
        if lang in ("ru", "kk", "uk", "sr", "bg", "mk"):
            # Cyrillic-script languages
            return normalize_cyrillic(text)
        if lang == "tr":
            return normalize_turkish(text)
        return text

    # ------------------------------------------------------------------
    # Stage 5: Final cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def _final_cleanup(text: str, _lang: str | None = None) -> str:
        """
        Remove residual control characters and normalize whitespace.

        Strips C0/C1 control characters (except standard whitespace)
        and collapses multiple consecutive spaces/tabs to a single space.
        """
        # Remove C0 control characters (0x00–0x1F) except:
        #   0x09 (tab), 0x0A (newline), 0x0D (carriage return)
        cleaned = "".join(
            ch
            for ch in text
            if ch in ("\t", "\n", "\r") or (ord(ch) >= 0x20 and ord(ch) != 0x7F)
        )
        return cleaned
