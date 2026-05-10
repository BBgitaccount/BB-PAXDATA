"""Unit tests for HedgingService."""

import pytest
from bb_paxdata.domain.enums import HedgingType
from bb_paxdata.domain.services.hedging_service import HedgingService


class TestHedgingService:
    """Test cases for HedgingService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = HedgingService()

    def test_hedging_service_initialization(self):
        """Test that HedgingService initializes correctly."""
        assert self.service is not None
        assert self.service.confidence == 1.0
        assert hasattr(self.service, "_patterns")

    def test_hedging_lexicon_coverage(self):
        """Test that hedging lexicon has all required categories."""
        lexicon = self.service.HEDGING_LEXICON

        required_categories = [
            "epistemic_high",
            "epistemic_medium",
            "anti_hedge",
            "approximator",
            "shield",
            "attribution",
        ]

        for category in required_categories:
            assert category in lexicon
            assert len(lexicon[category]) > 0

    def test_category_mapping(self):
        """Test that category mapping is complete."""
        mapping = self.service.CATEGORY_MAPPING

        required_categories = [
            "epistemic_high",
            "epistemic_medium",
            "anti_hedge",
            "approximator",
            "shield",
            "attribution",
        ]

        for category in required_categories:
            assert category in mapping
            assert isinstance(mapping[category], HedgingType)

    def test_analyze_hedging_epistemic_high(self):
        """Test hedging analysis with epistemic high terms."""
        text = "I think this might possibly work, perhaps."

        result = self.service.analyze_hedging(text)

        assert result.score > 0.0
        assert HedgingType.EPISTEMIC_HIGH in result.categories
        assert 0.0 <= result.score <= 1.0
        assert 0.0 <= result.confidence <= 1.0

    def test_analyze_hedging_epistemic_medium(self):
        """Test hedging analysis with epistemic medium terms."""
        text = "This typically happens in most cases."

        result = self.service.analyze_hedging(text)

        assert result.score > 0.0
        assert HedgingType.EPISTEMIC_MEDIUM in result.categories

    def test_analyze_hedging_anti_hedge(self):
        """Test hedging analysis with anti-hedge terms."""
        text = "This is definitely correct and certainly true."

        result = self.service.analyze_hedging(text)

        # Anti-hedge should reduce the score
        assert HedgingType.ANTI_HEDGE in result.categories
        # Score might be lower due to anti-hedge negative weight

    def test_analyze_hedging_approximator(self):
        """Test hedging analysis with approximator terms."""
        text = "The cost is approximately 100 dollars, roughly."

        result = self.service.analyze_hedging(text)

        assert result.score > 0.0
        assert HedgingType.APPROXIMATOR in result.categories

    def test_analyze_hedging_shield(self):
        """Test hedging analysis with shield terms."""
        text = "I'm not sure, but from my perspective, I could be wrong."

        result = self.service.analyze_hedging(text)

        assert result.score > 0.0
        assert HedgingType.SHIELD in result.categories

    def test_analyze_hedging_attribution(self):
        """Test hedging analysis with attribution terms."""
        text = "According to reports, it is allegedly said that..."

        result = self.service.analyze_hedging(text)

        assert result.score > 0.0
        assert HedgingType.ATTRIBUTION in result.categories

    def test_analyze_hedging_mixed_types(self):
        """Test hedging analysis with multiple hedging types."""
        text = "I think approximately 100 people, according to reports, might attend."

        result = self.service.analyze_hedging(text)

        assert len(result.categories) >= 2
        assert HedgingType.EPISTEMIC_HIGH in result.categories
        assert (
            HedgingType.APPROXIMATOR in result.categories
            or HedgingType.ATTRIBUTION in result.categories
        )

    def test_analyze_hedging_no_hedging(self):
        """Test hedging analysis with no hedging terms."""
        text = "This is a statement of fact."

        result = self.service.analyze_hedging(text)

        assert result.score == 0.0
        assert len(result.categories) == 0

    def test_analyze_hedging_case_insensitive(self):
        """Test that hedging detection is case insensitive."""
        text_lower = "i think this might work"
        text_upper = "I THINK THIS MIGHT WORK"

        result_lower = self.service.analyze_hedging(text_lower)
        result_upper = self.service.analyze_hedging(text_upper)

        assert result_lower.score == result_upper.score
        assert result_lower.categories == result_upper.categories

    def test_get_hedging_statistics(self):
        """Test detailed hedging statistics."""
        text = "I think this might work. Approximately 100 people will attend."

        stats = self.service.get_hedging_statistics(text)

        assert isinstance(stats, dict)
        assert "epistemic_high" in stats
        assert "approximator" in stats
        assert stats["epistemic_high"] > 0
        assert stats["approximator"] > 0

    def test_get_hedging_statistics_empty(self):
        """Test hedging statistics with no hedging."""
        text = "This is a simple statement."

        stats = self.service.get_hedging_statistics(text)

        for count in stats.values():
            assert count == 0

    def test_is_hedged_sentence(self):
        """Test hedged sentence detection."""
        hedged_text = "I think this might work."
        non_hedged_text = "This will work."

        assert self.service.is_hedged_sentence(hedged_text)
        assert not self.service.is_hedged_sentence(non_hedged_text)

    def test_is_hedged_sentence_threshold(self):
        """Test hedged sentence detection with custom threshold."""
        text = "This might work."  # Low hedging

        # Should be hedged with low threshold
        assert self.service.is_hedged_sentence(text, threshold=0.05)
        # Should not be hedged with high threshold
        assert not self.service.is_hedged_sentence(text, threshold=0.5)

    def test_get_dominant_hedging_type(self):
        """Test dominant hedging type detection."""
        text = "I think this might work. Perhaps we should consider it."

        dominant = self.service.get_dominant_hedging_type(text)

        assert dominant == HedgingType.EPISTEMIC_HIGH

    def test_get_dominant_hedging_type_none(self):
        """Test dominant hedging type with no hedging."""
        text = "This is a statement."

        dominant = self.service.get_dominant_hedging_type(text)

        assert dominant == HedgingType.NONE

    def test_analyze_hedging_word_boundary(self):
        """Test that hedging detection respects word boundaries."""
        text = "The think tank released a report."  # "think" should not match "I think"

        result = self.service.analyze_hedging(text)

        assert HedgingType.EPISTEMIC_HIGH not in result.categories

    def test_analyze_hedging_multi_word_phrases(self):
        """Test multi-word hedging phrase detection."""
        text = "According to reports, this is the case."

        result = self.service.analyze_hedging(text)

        assert HedgingType.ATTRIBUTION in result.categories

    def test_confidence_calculation(self):
        """Test confidence calculation based on matches."""
        # High hedging text should have high confidence
        high_hedging = "I think perhaps maybe this might possibly work."
        high_result = self.service.analyze_hedging(high_hedging)

        # Low hedging text should have lower confidence
        low_hedging = "This might work."
        low_result = self.service.analyze_hedging(low_hedging)

        assert high_result.confidence >= low_result.confidence

    def test_edge_case_very_hedged_text(self):
        """Test with very hedged text."""
        text = (
            "I think perhaps maybe possibly this might approximately work, "
            "according to reports."
        )

        result = self.service.analyze_hedging(text)

        assert result.score > 0.5
        assert len(result.categories) >= 3
        assert result.confidence > 0.5

    def test_edge_case_very_long_text(self):
        """Test with very long text."""
        text = "I think " * 100  # Repetitive hedging

        result = self.service.analyze_hedging(text)

        assert result.score > 0.0
        assert HedgingType.EPISTEMIC_HIGH in result.categories
        # Length normalization should keep score reasonable
        assert result.score <= 1.0

    def test_edge_case_special_characters(self):
        """Test hedging detection with special characters."""
        text = "I think... this might work! Perhaps?"

        result = self.service.analyze_hedging(text)

        assert result.score > 0.0
        assert HedgingType.EPISTEMIC_HIGH in result.categories

    def test_precompiled_patterns(self):
        """Test that patterns are precompiled correctly."""
        assert hasattr(self.service, "_patterns")
        assert len(self.service._patterns) == len(self.service.HEDGING_LEXICON)

        for _category, pattern in self.service._patterns.items():
            assert pattern is not None
            assert hasattr(pattern, "findall")


if __name__ == "__main__":
    pytest.main([__file__])
