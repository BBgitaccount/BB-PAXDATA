"""Unit tests for TopicService."""

from unittest.mock import patch

import pytest
from bb_paxdata.domain.enums import TopicCategory
from bb_paxdata.domain.services.topic_service import TopicService


class TestTopicService:
    """Test cases for TopicService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = TopicService()

    async def test_topic_service_initialization(self):
        """Test that TopicService initializes correctly."""
        assert self.service is not None
        assert self.service.confidence == 1.0
        assert hasattr(self.service, "KW_WEIGHTS")
        assert hasattr(self.service, "TOPICS")

    async def test_topics_coverage(self):
        """Test that topics dictionary has all required topics."""
        topics = self.service.TOPICS

        required_topics = [
            "BM_Reformu",
            "Güvenlik_Çatışma",
            "Ekonomi_Ticaret_Enerji",
            "Liderlik_Yönetim",
            "Diplomatik_Çözüm",
            "AB_NATO_Genişleme",
            "Yapay_Zeka_Teknoloji",
            "Orta_Güçler_Bölgesel",
            "Gazze_Filistin_İsrail",
            "Ukrayna_Rusya",
            "Suriye_Geçiş",
            "Afrika_Ortadoğu",
            "İnsani_Yardım_Haklar",
            "Çok_Kutupluluk_Düzen",
            "Risk_Kırılım",
        ]

        for topic in required_topics:
            assert topic in topics
            assert len(topics[topic]) > 0

    async def test_keyword_weights_calculation(self):
        """Test that keyword weights are calculated correctly."""
        weights = self.service.KW_WEIGHTS

        # Should have weights for all keywords
        all_keywords = []
        for keywords in self.service.TOPICS.values():
            all_keywords.extend(keywords)

        for keyword in all_keywords:
            assert keyword in weights
            assert weights[keyword] > 0.0

    async def test_weighted_topic_score_basic(self):
        """Test basic weighted topic scoring."""
        text = "united nations security council reform"

        scores = self.service.weighted_topic_score(text)

        assert isinstance(scores, dict)
        assert "BM_Reformu" in scores
        assert scores["BM_Reformu"] > 0.0

    async def test_weighted_topic_score_multiple_topics(self):
        """Test topic scoring with multiple topic matches."""
        text = "united nations security council reform and economic cooperation"

        scores = self.service.weighted_topic_score(text)

        assert scores["BM_Reformu"] > 0.0
        assert scores["Ekonomi_Ticaret_Enerji"] > 0.0

    async def test_weighted_topic_score_with_tfidf(self):
        """Test topic scoring with TF-IDF enhancement."""
        text = "united nations security council reform"
        tfidf_keywords = ["united nations", "security council", "reform"]

        scores = self.service.weighted_topic_score(text, tfidf_keywords)

        assert scores["BM_Reformu"] > 0.0
        # Should be higher than without TF-IDF due to bonus
        scores_without_tfidf = self.service.weighted_topic_score(text)
        assert scores["BM_Reformu"] >= scores_without_tfidf["BM_Reformu"]

    async def test_weighted_topic_score_no_matches(self):
        """Test topic scoring with no keyword matches."""
        text = "This is a simple sentence with no topic keywords."

        scores = self.service.weighted_topic_score(text)

        for score in scores.values():
            assert score == 0.0

    async def test_topic_specificity_single_topic(self):
        """Test topic specificity with single dominant topic."""
        scores = {"BM_Reformu": 10.0, "Güvenlik_Çatışma": 0.0}

        specificity = self.service.topic_specificity(scores)

        assert specificity == 1.0  # Perfect specificity

    async def test_topic_specificity_multiple_topics(self):
        """Test topic specificity with multiple topics."""
        scores = {"BM_Reformu": 5.0, "Güvenlik_Çatışma": 5.0}

        specificity = self.service.topic_specificity(scores)

        assert specificity == 0.0  # Zero specificity for equal scores

    async def test_topic_specificity_no_topics(self):
        """Test topic specificity with no topic scores."""
        scores = {}

        specificity = self.service.topic_specificity(scores)

        assert specificity == 0.0

    async def test_topic_specificity_equal_distribution(self):
        """Test topic specificity with equal distribution."""
        scores = {
            "BM_Reformu": 1.0,
            "Güvenlik_Çatışma": 1.0,
            "Ekonomi_Ticaret_Enerji": 1.0,
        }

        specificity = self.service.topic_specificity(scores)

        # Should be low specificity due to equal distribution
        assert specificity < 0.5

    async def test_get_dominant_topic_basic(self):
        """Test dominant topic identification."""
        scores = {"BM_Reformu": 5.0, "Güvenlik_Çatışma": 2.0}

        dominant = self.service.get_dominant_topic(scores)

        assert dominant == TopicCategory.BM_REFORUMU

    async def test_get_dominant_topic_no_scores(self):
        """Test dominant topic with no scores."""
        scores = {}

        dominant = self.service.get_dominant_topic(scores)

        assert dominant == TopicCategory.NONE

    async def test_get_dominant_topic_all_zeros(self):
        """Test dominant topic with all zero scores."""
        scores = {"BM_Reformu": 0.0, "Güvenlik_Çatışma": 0.0}

        dominant = self.service.get_dominant_topic(scores)

        assert dominant == TopicCategory.NONE

    async def test_get_dominant_topic_mapping(self):
        """Test that all topics map to categories correctly."""
        for topic_name in self.service.TOPICS.keys():
            scores = {topic_name: 1.0}
            dominant = self.service.get_dominant_topic(scores)
            assert dominant != TopicCategory.NONE

    async def test_tfidf_batch_without_sklearn(self):
        """Test TF-IDF batch processing without scikit-learn."""
        texts = ["text one", "text two", "text three"]

        with patch(
            "bb_paxdata.domain.services.topic_service.TopicService.HAS_TFIDF", False
        ):
            result = self.service.tfidf_batch(texts)

        assert len(result) == len(texts)
        assert all(keywords == [] for keywords in result)

    @patch("bb_paxdata.domain.services.topic_service.TopicService.HAS_TFIDF", True)
    async def test_tfidf_batch_with_sklearn_import_error(self):
        """Test TF-IDF batch processing with ImportError."""
        texts = ["text one", "text two"]

        with patch.dict("sys.modules", {"sklearn.feature_extraction.text": None}):
            result = self.service.tfidf_batch(texts)

        assert len(result) == len(texts)
        assert all(keywords == [] for keywords in result)

    async def test_analyze_topics_basic(self):
        """Test basic topic analysis."""
        text = "united nations security council reform"

        result = self.service.analyze_topics(text)

        assert result is not None
        assert hasattr(result, "topic_scores")
        assert hasattr(result, "dominant_topic")
        assert hasattr(result, "specificity")
        assert hasattr(result, "confidence")

        assert result.dominant_topic == TopicCategory.BM_REFORUMU
        assert result.specificity > 0.0
        assert 0.0 <= result.confidence <= 1.0

    async def test_analyze_topics_with_tfidf(self):
        """Test topic analysis with TF-IDF keywords."""
        text = "united nations security council reform"
        tfidf_keywords = ["united nations", "security council"]

        result = self.service.analyze_topics(text, tfidf_keywords)

        assert result.dominant_topic == TopicCategory.BM_REFORUMU
        assert result.specificity > 0.0

    async def test_analyze_topics_no_keywords(self):
        """Test topic analysis with no matching keywords."""
        text = "This is a simple sentence."

        result = self.service.analyze_topics(text)

        assert result.dominant_topic == TopicCategory.NONE
        assert result.specificity == 0.0
        assert result.confidence == 0.0

    async def test_analyze_topics_complex_text(self):
        """Test topic analysis with complex text."""
        text = (
            "The united nations security council reform is important for "
            "global peace and economic cooperation."
        )

        result = self.service.analyze_topics(text)

        assert result.dominant_topic == TopicCategory.BM_REFORUMU
        assert result.specificity > 0.0
        assert result.confidence > 0.0

    async def test_confidence_calculation(self):
        """Test confidence calculation."""
        # High specificity text
        high_specificity_text = "united nations security council reform veto charter"
        high_result = self.service.analyze_topics(high_specificity_text)

        # Low specificity text
        low_specificity_text = "united nations economic cooperation security council"
        low_result = self.service.analyze_topics(low_specificity_text)

        # High specificity should have higher confidence
        assert high_result.confidence >= low_result.confidence

    async def test_edge_case_very_long_text(self):
        """Test topic analysis with very long text."""
        text = "united nations security council " * 50

        result = self.service.analyze_topics(text)

        assert result.dominant_topic == TopicCategory.BM_REFORUMU
        assert result.specificity > 0.0

    async def test_edge_case_special_characters(self):
        """Test topic analysis with special characters."""
        text = "The united nations security council reform is important!"

        result = self.service.analyze_topics(text)

        assert result.dominant_topic == TopicCategory.BM_REFORUMU

    async def test_edge_case_mixed_case(self):
        """Test topic analysis with mixed case."""
        text_lower = "united nations security council reform"
        text_upper = "UNITED NATIONS SECURITY COUNCIL REFORM"
        text_mixed = "United Nations Security Council Reform"

        result_lower = self.service.analyze_topics(text_lower)
        result_upper = self.service.analyze_topics(text_upper)
        result_mixed = self.service.analyze_topics(text_mixed)

        assert (
            result_lower.dominant_topic
            == result_upper.dominant_topic
            == result_mixed.dominant_topic
        )

    async def test_infer_topic(self):
        """Test topic inference from text."""
        text = "united nations security council reform"

        inferred_topic = self.service.analyze_topics(text).dominant_topic

        assert inferred_topic == TopicCategory.BM_REFORUMU

    async def test_infer_topic_no_match(self):
        """Test topic inference with no matching topic."""
        text = "This is a simple sentence."

        inferred_topic = self.service.analyze_topics(text).dominant_topic

        assert inferred_topic == TopicCategory.NONE

    async def test_phrase_bonus_in_weights(self):
        """Test that multi-word phrases get weight bonus."""
        # Find a multi-word phrase and single word
        multi_word_phrase = None
        single_word = None

        for keywords in self.service.TOPICS.values():
            for keyword in keywords:
                if " " in keyword and not multi_word_phrase:
                    multi_word_phrase = keyword
                elif " " not in keyword and not single_word:
                    single_word = keyword

        if multi_word_phrase and single_word:
            # Multi-word phrase should have higher weight
            assert (
                self.service.KW_WEIGHTS[multi_word_phrase]
                > self.service.KW_WEIGHTS[single_word]
            )


if __name__ == "__main__":
    pytest.main([__file__])
