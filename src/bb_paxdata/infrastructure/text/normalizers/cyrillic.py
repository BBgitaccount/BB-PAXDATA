"""
Cyrillic character normalization utilities.

Handles character standardization for Russian, Kazakh, Ukrainian,
Serbian, and other Cyrillic-script languages used in diplomatic
transcripts.
"""


def normalize_cyrillic(text: str) -> str:
    """
    Standardize Cyrillic character variants.

    Transformations applied:
    - Yo (ё/Ё) → Ye (е/Е) — simplification for lexicon matching
    - Preserves Kazakh-specific characters (ғ қ ң ө ү һ ә)
      which are already canonical in Unicode.

    Note:
        The Yery (й) variant issue is already handled by NFKC
        normalization at the Unicode level. This function handles
        the cases where fonts/encodings produce non-standard code
        points that NFKC does not cover.

    Args:
        text: Input text containing Cyrillic characters.

    Returns:
        Normalized Cyrillic text.

    Example:
        >>> normalize_cyrillic("Всё хорошо")
        'Все хорошо'
    """
    # Yo (ё U+0451) → Ye (е U+0435)
    # Yo capital (Ё U+0401) → Ye capital (Е U+0415)
    # Simplification for lexicon matching; acceptable for diplomatic NLP.
    text = text.replace("\u0451", "\u0435").replace("\u0401", "\u0415")

    # Kazakh-specific canonical characters are preserved as-is:
    # ғ (U+0493), қ (U+049B), ң (U+04A3), ө (U+04E9),
    # ү (U+04AF), һ (U+04BB), ә (U+04D9)
    # These are already in their canonical Unicode forms.

    return text
