import unicodedata

from bb_paxdata.infrastructure.text.normalizer import normalize_person_name


def test_normalize_person_name_basic():
    assert normalize_person_name("LEVENT GÜMRÜKÇÜ") == "LEVENT GÜMRÜKÇÜ"
    assert normalize_person_name("LIZZY, Porter") == "LIZZY, Porter"


def test_normalize_person_name_combining_characters():
    # I + combining dot above (U+0307) -> should normalize to İ via NFC
    combining_name = "I\u0307SMAIL"
    normalized = normalize_person_name(combining_name)
    # The NFC normalization combines I and \u0307 into \u0130 (İ)
    assert unicodedata.normalize("NFC", normalized) == normalized
    assert "İ" in normalized
    assert normalized == "İSMAIL"


def test_normalize_person_name_removes_invalid_chars():
    # Remove weird symbols and characters but keep Turkish/Latin letters, space, hyphen, dot, comma
    assert normalize_person_name("Mevlüt Çavuşoğlu @FM") == "Mevlüt Çavuşoğlu FM"
    assert normalize_person_name("Hakan Fidan (Turkish FM)") == "Hakan Fidan Turkish FM"
