"""Unit tests for SentimentService."""

from unittest.mock import Mock, patch

import pytest
from bb_paxdata.domain.enums import SentimentCategory
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.domain.services.sentiment_service import SentimentService


class TestSentimentService:
    """Test cases for SentimentService."""

    async def setup_method(self):
        """Set up test fixtures."""
        self.service = SentimentService()

    async def test_sentiment_service_initialization(self):
        """Test that SentimentService initializes correctly."""
        assert self.service is not None
        assert hasattr(self.service, "_vader_analyzer")
        assert self.service.confidence == 1.0

    async def test_tokenize_words_basic(self):
        """Test basic word tokenization."""
        text = "This is a simple test sentence."
        tokens = self.service.tokenize_words(text)
        expected = ["this", "is", "a", "simple", "test", "sentence"]
        assert tokens == expected

    async def test_tokenize_words_with_contractions(self):
        """Test tokenization with contractions."""
        text = "We don't want war, but we can't accept this."
        tokens = self.service.tokenize_words(text)
        # Contractions should be handled
        assert "don_t" in tokens or "don't" in tokens
        assert "can_t" in tokens or "can't" in tokens

    async def test_diplo_sentiment_positive(self):
        """Test DIPLO sentiment analysis with positive text."""
        text = "We seek comprehensive peace and cooperation."
        score = self.service.diplo_sentiment(text)
        assert score > 0.0
        assert score <= 1.0

    async def test_diplo_sentiment_negative(self):
        """Test DIPLO sentiment analysis with negative text."""
        text = "This aggression and war must stop."
        score = self.service.diplo_sentiment(text)
        assert score < 0.0
        assert score >= -1.0

    async def test_diplo_sentiment_neutral(self):
        """Test DIPLO sentiment analysis with neutral text."""
        text = "The meeting was held yesterday."
        score = self.service.diplo_sentiment(text)
        assert score == 0.0

    async def test_negation_aware_diplo_with_negation(self):
        """Test negation-aware DIPLO sentiment with negation."""
        text = "We do not want war."
        score = self.service.negation_aware_diplo(text)
        # "war" is negative, but negated should make it positive
        assert score > 0.0

    async def test_negation_aware_diplo_without_negation(self):
        """Test negation-aware DIPLO sentiment without negation."""
        text = "We want peace."
        score = self.service.negation_aware_diplo(text)
        # "peace" is positive, no negation
        assert score > 0.0

    async def test_negation_aware_diplo_negation_window(self):
        """Test negation window functionality."""
        text = "We do not want this war, but we accept peace."
        score = self.service.negation_aware_diplo(text)
        # "war" should be negated (within window), "peace" should be positive
        # Overall sentiment should be mixed but leaning positive
        assert score > -0.5

    async def test_classify_emotion_extreme_negative(self):
        """Test emotion classification for extreme negative."""
        emotion = self.service._classify_emotion(-0.8)
        assert emotion == SentimentCategory.HOSTILE

    async def test_classify_emotion_negative(self):
        """Test emotion classification for negative."""
        emotion = self.service._classify_emotion(-0.4)
        assert emotion == SentimentCategory.NEGATIVE

    async def test_classify_emotion_concerned(self):
        """Test emotion classification for concerned."""
        emotion = self.service._classify_emotion(-0.2)
        assert emotion == SentimentCategory.CONCERNED

    async def test_classify_emotion_neutral(self):
        """Test emotion classification for neutral."""
        emotion = self.service._classify_emotion(0.0)
        assert emotion == SentimentCategory.NEUTRAL

    async def test_classify_emotion_positive(self):
        """Test emotion classification for positive."""
        emotion = self.service._classify_emotion(0.2)
        assert emotion == SentimentCategory.POSITIVE

    async def test_classify_emotion_optimistic(self):
        """Test emotion classification for optimistic."""
        emotion = self.service._classify_emotion(0.5)
        assert emotion == SentimentCategory.OPTIMISTIC

    async def test_classify_emotion_cooperative(self):
        """Test emotion classification for cooperative."""
        emotion = self.service._classify_emotion(0.8)
        assert emotion == SentimentCategory.COOPERATIVE

    @patch("vaderSentiment.vaderSentiment.SentimentIntensityAnalyzer")
    async def test_analyze_sentence_basic(self, mock_vader):
        """Test basic sentence analysis."""
        # Mock VADER response
        mock_analyzer = Mock()
        mock_analyzer.polarity_scores.return_value = {
            "compound": 0.1,
            "pos": 0.2,
            "neg": 0.1,
            "neu": 0.7,
        }
        mock_vader.return_value = mock_analyzer

        service = SentimentService()
        sentence = Sentence(id="1", text="We want peace.")

        result = service.analyze(sentence)

        assert result is not None
        assert hasattr(result, "score")
        assert hasattr(result, "emotion_category")
        assert hasattr(result, "negation_aware_score")
        assert hasattr(result, "confidence")
        assert -1.0 <= result.score <= 1.0
        assert -1.0 <= result.negation_aware_score <= 1.0
        assert 0.0 <= result.confidence <= 1.0

    async def test_analyze_sentence_with_negation(self):
        """Test sentence analysis with negation."""
        sentence = Sentence(id="1", text="We do not want war.")

        result = self.service.analyze(sentence)

        assert result.negation_aware_score > 0.0  # Should be positive due to negation
        assert result.emotion_category in [
            SentimentCategory.POSITIVE,
            SentimentCategory.OPTIMISTIC,
        ]

    async def test_analyze_sentence_empty_text(self):
        """Test sentence analysis with empty text."""
        sentence = Sentence(id="1", text="")

        result = self.service.analyze(sentence)

        assert result.score == 0.0
        assert result.negation_aware_score == 0.0
        assert result.emotion_category == SentimentCategory.NEUTRAL

    async def test_analyze_sentence_complex_diplomatic_text(self):
        """Test analysis with complex diplomatic text."""
        text = (
            "While we cannot accept this aggression, we remain committed to "
            "diplomatic dialogue and seek peaceful cooperation."
        )
        sentence = Sentence(id="1", text=text)

        result = self.service.analyze(sentence)

        # Should detect mixed sentiment with overall leaning
        assert -1.0 <= result.score <= 1.0
        assert -1.0 <= result.negation_aware_score <= 1.0
        assert result.confidence > 0.0  # Should have some confidence

    async def test_diplo_lexicon_coverage(self):
        """Test that DIPLO lexicon has good coverage."""
        lexicon = self.service.DIPLO_LEXICON

        # Check for key diplomatic terms
        assert "peace" in lexicon
        assert "war" in lexicon
        assert "conflict" in lexicon
        assert "cooperation" in lexicon
        assert "aggression" in lexicon

        # Check that scores are in expected range
        for _term, score in lexicon.items():
            assert -1.0 <= score <= 1.0

    async def test_negation_words_coverage(self):
        """Test that negation words list is comprehensive."""
        negation_words = self.service.NEGATION_WORDS

        # Check for common negations
        assert "not" in negation_words
        assert "no" in negation_words
        assert "never" in negation_words
        assert "cannot" in negation_words
        assert "don't" in negation_words

    async def test_confidence_calculation(self):
        """Test confidence calculation based on method agreement."""
        # Test with similar scores (high confidence)
        text = "peace cooperation"
        sentence = Sentence(id="1", text=text)

        result = self.service.analyze(sentence)

        # Should have reasonable confidence
        assert result.confidence > 0.3

    async def test_edge_case_very_long_sentence(self):
        """Test analysis with very long sentence."""
        text = "peace " * 100  # Long repetitive text
        sentence = Sentence(id="1", text=text)

        result = self.service.analyze(sentence)

        assert result is not None
        assert result.score > 0.0  # Should be very positive

    async def test_edge_case_special_characters(self):
        """Test analysis with special characters."""
        text = "We want peace! Cooperation... not war?"
        sentence = Sentence(id="1", text=text)

        result = self.service.analyze(sentence)

        assert result is not None
        assert -1.0 <= result.score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__])
