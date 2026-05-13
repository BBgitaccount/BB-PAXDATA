"""
Arabic character normalization utilities.

Standardizes Arabic letter variants to their canonical forms,
removes diacritical marks (tashkeel), and handles Persian/Arabic
character mapping for consistent NLP processing.
"""

import re


def normalize_arabic(text: str) -> str:
    """
    Standardize Arabic letter variants to their canonical forms.

    Transformations applied:
    - Alef variants (أ إ آ) → canonical Alef (ا)
    - Te marbuta (ة) → He (ه)
    - Persian Kaf (ک) → Arabic Kaf (ك)
    - Yeh variants (ی ى) → standard Yeh (ي)
    - Remove tashkeel (diacritical marks / harakat)

    Args:
        text: Input text containing Arabic characters.

    Returns:
        Normalized Arabic text with canonical character forms.

    Example:
        >>> normalize_arabic("الرئيسُ")
        'الرئيس'
    """
    # Alef variants → canonical Alef (U+0627)
    # U+0622 (آ), U+0623 (أ), U+0625 (إ) → U+0627 (ا)
    text = re.sub(r"[\u0622\u0623\u0625]", "\u0627", text)

    # Te marbuta (ة U+0629) → He (ه U+0647)
    text = text.replace("\u0629", "\u0647")

    # Persian Kaf (ک U+06A9) → Arabic Kaf (ك U+0643)
    text = text.replace("\u06a9", "\u0643")

    # Yeh variants:
    # U+06CC (ی Farsi Yeh), U+06D2 (ے Yeh Barree) → U+064A (ي)
    text = re.sub(r"[\u06cc\u06d2]", "\u064a", text)

    # Remove tashkeel (diacritical marks / harakat)
    # U+064B–U+065F (fathatan, dammatan, kasratan, fatha, damma, kasra,
    # shadda, sukun, etc.) and U+0670 (superscript alef)
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)

    return text
