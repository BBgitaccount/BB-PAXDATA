"""
Unit tests for EncodingNormalizer.

Tests cover:
- Stage 1: BOM and NULL byte removal
- Stage 2: Mojibake correction (ftfy)
- Stage 3: Unicode NFKC normalization
- Stage 4: Language-specific normalization (Arabic, Cyrillic, Turkish)
- Idempotency property: normalize(normalize(x)) == normalize(x)
"""

import pytest
from bb_paxdata.infrastructure.text.encoding_normalizer import EncodingNormalizer
from bb_paxdata.infrastructure.text.normalizers.arabic import normalize_arabic
from bb_paxdata.infrastructure.text.normalizers.cyrillic import normalize_cyrillic
from bb_paxdata.infrastructure.text.normalizers.turkish import normalize_turkish


@pytest.fixture
def normalizer() -> EncodingNormalizer:
    return EncodingNormalizer()


# ---------------------------------------------------------------------------
# Stage 1: BOM & binary cleanup
# ---------------------------------------------------------------------------


class TestBOMRemoval:
    def test_removes_utf8_bom(self, normalizer: EncodingNormalizer) -> None:
        text = "\ufeffHello World"
        result = normalizer.normalize(text)
        assert not result.startswith("\ufeff")
        assert result.startswith("Hello")

    def test_removes_null_bytes(self, normalizer: EncodingNormalizer) -> None:
        text = "Hello\x00World"
        result = normalizer.normalize(text)
        assert "\x00" not in result
        assert "HelloWorld" in result

    def test_clean_text_unchanged(self, normalizer: EncodingNormalizer) -> None:
        text = "This is a clean diplomatic statement."
        result = normalizer.normalize(text)
        assert result == text


# ---------------------------------------------------------------------------
# Stage 2: Mojibake correction
# ---------------------------------------------------------------------------


class TestMojibakeCorrection:
    def test_turkish_mojibake(self, normalizer: EncodingNormalizer) -> None:
        """'TÃ¼rkiye' is classic UTF-8 read as Latin-1."""
        mojibake = "T\xc3\xbcrkiye"  # bytes b'\xc3\xbc' decoded as latin-1
        # ftfy.fix_text should resolve this
        result = normalizer.normalize(mojibake)
        # Result should be human-readable (no Ã¼ pattern)
        assert "\xc3" not in result or "ü" in result

    def test_clean_english_unchanged(self, normalizer: EncodingNormalizer) -> None:
        text = "The United Nations Security Council condemns aggression."
        result = normalizer.normalize(text, detected_lang="en")
        assert result == text


# ---------------------------------------------------------------------------
# Stage 3: Unicode NFKC
# ---------------------------------------------------------------------------


class TestUnicodeNFKC:
    def test_ligature_expansion(self, normalizer: EncodingNormalizer) -> None:
        """ﬁ (U+FB01) should become 'fi'."""
        text = "\ufb01nancial"
        result = normalizer.normalize(text)
        assert result == "financial"

    def test_fullwidth_to_halfwidth(self, normalizer: EncodingNormalizer) -> None:
        """Full-width characters should be normalized."""
        text = "\uff41\uff42\uff43"  # ａｂｃ
        result = normalizer.normalize(text)
        assert result == "abc"


# ---------------------------------------------------------------------------
# Stage 4a: Arabic normalization
# ---------------------------------------------------------------------------


class TestArabicNormalization:
    def test_alef_variants_normalized(self) -> None:
        """أ (U+0623) and إ (U+0625) should become ا (U+0627)."""
        text = "أإآ"
        result = normalize_arabic(text)
        assert result == "\u0627\u0627\u0627"

    def test_te_marbuta_removed(self) -> None:
        """ة (U+0629) should become ه (U+0647)."""
        text = "دولة"
        result = normalize_arabic(text)
        assert "\u0629" not in result
        assert result.endswith("\u0647")

    def test_tashkeel_removed(self) -> None:
        """Diacritical marks (fatha, damma, kasra etc.) should be removed."""
        text = "الرئيسُ"  # Has damma (U+064F)
        result = normalize_arabic(text)
        assert "\u064f" not in result

    def test_via_normalizer_with_lang(self, normalizer: EncodingNormalizer) -> None:
        text = "أمريكا"
        result = normalizer.normalize(text, detected_lang="ar")
        assert "\u0623" not in result  # أ should be gone


# ---------------------------------------------------------------------------
# Stage 4b: Cyrillic normalization
# ---------------------------------------------------------------------------


class TestCyrillicNormalization:
    def test_yo_to_ye(self) -> None:
        """ё (U+0451) should become е (U+0435)."""
        assert normalize_cyrillic("ёлка") == "елка"

    def test_yo_capital_to_ye_capital(self) -> None:
        """Ё (U+0401) should become Е (U+0415)."""
        assert normalize_cyrillic("Ёлка") == "Елка"

    def test_kazakh_chars_preserved(self) -> None:
        """Kazakh-specific Cyrillic chars should be unchanged."""
        text = "ғқңөүһә"
        result = normalize_cyrillic(text)
        assert result == text


# ---------------------------------------------------------------------------
# Stage 4c: Turkish normalization
# ---------------------------------------------------------------------------


class TestTurkishNormalization:
    def test_right_single_quote_normalized(self) -> None:
        """' (U+2019) → ' (U+0027)."""
        text = "Türkiye\u2019nin"
        result = normalize_turkish(text)
        assert "\u2019" not in result
        assert "Türkiye'nin" == result

    def test_backtick_normalized(self) -> None:
        """Backtick → straight apostrophe."""
        text = "NATO`ya"
        result = normalize_turkish(text)
        assert "`" not in result
        assert "NATO'ya" == result

    def test_left_single_quote_normalized(self) -> None:
        """' (U+2018) → ' (U+0027)."""
        text = "BM\u2018de"
        result = normalize_turkish(text)
        assert "\u2018" not in result

    def test_via_normalizer_with_lang(self, normalizer: EncodingNormalizer) -> None:
        text = "Türkiye\u2019nin toprak bütünlüğü"
        result = normalizer.normalize(text, detected_lang="tr")
        assert "\u2019" not in result


# ---------------------------------------------------------------------------
# Idempotency property tests
# ---------------------------------------------------------------------------


class TestIdempotency:
    @pytest.mark.parametrize(
        "text,lang",
        [
            ("The Security Council unanimously adopted Resolution 2758.", "en"),
            ("Türkiye Cumhuriyeti'nin tutumu net.", "tr"),
            ("الأمم المتحدة", "ar"),
            ("Президент России", "ru"),
            ("Normal plain ASCII text.", None),
        ],
    )
    def test_normalize_is_idempotent(
        self,
        normalizer: EncodingNormalizer,
        text: str,
        lang: str | None,
    ) -> None:
        """normalize(normalize(x)) == normalize(x) must hold."""
        once = normalizer.normalize(text, lang)
        twice = normalizer.normalize(once, lang)
        assert once == twice, f"Not idempotent for lang={lang!r}: {text!r}"
