import re
import unicodedata


def normalize_person_name(name: str) -> str:
    """
    Normalizes a person name for BB-PAXDATA.

    Specifically handles Turkish combining characters and removes
    all characters except Turkish/Latin alphabets, numbers, spaces,
    dots, commas, and hyphens.
    """
    if not name:
        return ""

    # 1. Unicode NFC normalization (combines base character + combining mark,
    # e.g., I + U+0307 combining dot above -> İ)
    name = unicodedata.normalize("NFC", name)

    # 2. Keep only letters (including Turkish), numbers, spaces, dots, commas, and hyphens
    # Sadece Türkçe + latin alfabe + boşluk + tire + nokta + virgül bırak
    cleaned = re.sub(r"[^\w\s\-.,ÇçĞğİışŞşÜüÖö]", "", name)

    # 3. Clean multiple spaces and return
    return " ".join(cleaned.split())
