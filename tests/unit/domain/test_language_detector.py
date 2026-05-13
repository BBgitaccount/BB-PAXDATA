"""
Unit tests for LanguageDetector and LanguageRouter.
"""

from unittest.mock import MagicMock, patch

from bb_paxdata.domain.services.language_detector import LanguageDetector
from bb_paxdata.domain.services.language_router import LanguageRouter
from langdetect.lang_detect_exception import LangDetectException  # type: ignore


class TestLanguageDetector:
    def test_detect_turkish(self) -> None:
        text = "Türkiye, uluslararası barış ve güvenliğin korunmasına önem vermektedir."
        assert LanguageDetector.detect(text) == "tr"

    def test_detect_english(self) -> None:
        text = "The United States strongly condemns these aggressive actions."
        assert LanguageDetector.detect(text) == "en"

    def test_detect_arabic_fallback_via_script(self) -> None:
        """
        We don't support Arabic via SpaCy yet, so the detector should
        identify the script and return 'ar' as fallback if langdetect
        somehow fails or returns a different variant.
        Even if langdetect returns 'ar', we want to make sure it handles it.
        """
        text = "الأمم المتحدة تدين أعمال العنف."
        # langdetect might naturally return 'ar'. If not, our script detector will.
        lang = LanguageDetector.detect(text)
        assert lang == "ar"

    def test_detect_cyrillic_fallback_via_script(self) -> None:
        """Testing Cyrillic script fallback."""
        text = "Россия призывает к мирному диалогу."
        lang = LanguageDetector.detect(text)
        assert lang == "ru"

    def test_empty_string_returns_fallback(self) -> None:
        assert LanguageDetector.detect("") == "en"
        assert LanguageDetector.detect("   \n   ") == "en"

    @patch("bb_paxdata.domain.services.language_detector.detect")
    def test_langdetect_exception_returns_fallback(
        self, mock_detect: MagicMock
    ) -> None:
        """If langdetect throws an exception, it should fail gracefully."""
        mock_detect.side_effect = LangDetectException(0, "No features in text.")
        assert LanguageDetector.detect("12345 !@#$") == "en"

    @patch("bb_paxdata.domain.services.language_detector.detect")
    def test_unsupported_language_without_script_match(
        self, mock_detect: MagicMock
    ) -> None:
        """If langdetect returns 'zh-cn' (Chinese), we fallback to 'en'."""
        mock_detect.return_value = "zh-cn"
        assert LanguageDetector.detect("你好世界") == "en"


class TestLanguageRouter:
    def test_get_config_turkish(self) -> None:
        config = LanguageRouter.get_config("tr")
        assert config.spacy_model == "tr_core_news_trf"
        assert config.sentiment_lexicon == "DIPLO_LEXICON_TR"

    def test_get_config_english(self) -> None:
        config = LanguageRouter.get_config("en")
        assert config.spacy_model == "en_core_web_trf"
        assert config.sentiment_lexicon == "DIPLO_LEXICON"

    def test_get_config_unsupported_falls_back_to_english(self) -> None:
        config = LanguageRouter.get_config("ar")
        # Should return English config by default
        assert config.spacy_model == "en_core_web_trf"

    def test_supported_languages_list(self) -> None:
        langs = LanguageRouter.supported_languages()
        assert "tr" in langs
        assert "en" in langs
        assert "ar" not in langs

    def test_has_spacy_model(self) -> None:
        assert LanguageRouter.has_spacy_model("tr") is True
        assert LanguageRouter.has_spacy_model("en") is True
        assert LanguageRouter.has_spacy_model("ar") is False
