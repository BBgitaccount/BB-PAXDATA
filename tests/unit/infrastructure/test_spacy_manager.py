"""
Unit tests for SpacyModelManager.
"""

from unittest.mock import MagicMock, patch

from bb_paxdata.infrastructure.nlp.spacy_manager import SpacyModelManager


class TestSpacyModelManager:
    @patch("spacy.load")
    def test_get_model_loads_once(self, mock_spacy_load: MagicMock) -> None:
        # Setup
        mock_nlp = MagicMock()
        mock_spacy_load.return_value = mock_nlp

        # Clear any existing models
        SpacyModelManager.unload_all()

        # Execute
        model1 = SpacyModelManager.get_model("en")
        model2 = SpacyModelManager.get_model("en")

        # Assert
        assert model1 == mock_nlp
        assert model2 == mock_nlp
        assert mock_spacy_load.call_count == 1
        mock_spacy_load.assert_called_once()

    @patch("spacy.load")
    def test_unload_removes_from_cache(self, mock_spacy_load: MagicMock) -> None:
        # Setup
        mock_nlp = MagicMock()
        mock_spacy_load.return_value = mock_nlp
        SpacyModelManager.unload_all()

        # Execute
        SpacyModelManager.get_model("tr")
        assert "tr" in SpacyModelManager._models

        SpacyModelManager.unload("tr")

        # Assert
        assert "tr" not in SpacyModelManager._models

    @patch("spacy.load")
    def test_fallback_to_english(self, mock_spacy_load: MagicMock) -> None:
        # Setup
        mock_nlp = MagicMock()
        mock_spacy_load.return_value = mock_nlp
        SpacyModelManager.unload_all()

        # Execute
        # "fr" is not in SPACY_PIPELINES, so it should fallback to "en"
        model = SpacyModelManager.get_model("fr")

        # Assert
        assert model == mock_nlp
        # Verify it was loaded as English
        mock_spacy_load.assert_called_with(
            "en_core_web_trf", disable=["attribute_ruler", "lemmatizer"]
        )
