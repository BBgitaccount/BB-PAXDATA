"""
Turkish character normalization utilities.

Handles Turkish-specific character consistency issues:
- Apostrophe variant standardization (curly/backtick → straight)
- Dotted/dotless-I handling notes

Note on dotted/dotless I:
    Unicode NFKC preserves İ (U+0130) and ı (U+0131) correctly.
    In the rare case where a system replaces İ with Latin I (U+0049),
    automated correction is risky without word-level context.
    Such cases require manual review in diplomatic transcripts.
"""


def normalize_turkish(text: str) -> str:
    """
    Standardize Turkish-specific character variants.

    Transformations applied:
    - Right single quotation mark (') → straight apostrophe (')
    - Backtick (`) → straight apostrophe (')
    - Left single quotation mark (') → straight apostrophe (')

    These apostrophe variants appear in Turkish proper-noun suffixes:
    "Türkiye'nin", "NATO'ya", "BM'de" etc.

    Args:
        text: Input text containing Turkish characters.

    Returns:
        Normalized Turkish text with consistent apostrophes.

    Example:
        >>> normalize_turkish("Türkiye\u2019nin")
        "Türkiye'nin"
    """
    # Right single quotation mark (') U+2019 → straight apostrophe
    text = text.replace("\u2019", "'")
    # Left single quotation mark (') U+2018 → straight apostrophe
    text = text.replace("\u2018", "'")
    # Backtick (`) U+0060 → straight apostrophe
    text = text.replace("`", "'")
    # Prime character (′) U+2032 → straight apostrophe (rare in OCR)
    text = text.replace("\u2032", "'")

    return text
