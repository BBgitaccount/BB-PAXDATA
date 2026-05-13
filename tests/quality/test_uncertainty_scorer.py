"""Tests for UncertaintyScorer."""

from unittest.mock import AsyncMock

import pytest
from bb_paxdata.quality.consistency import ConsistencyCalculator
from bb_paxdata.quality.uncertainty import UncertaintyScorer


class TestConsistencyCalculator:
    """Test consistency calculation utilities."""

    def test_numeric_consistency_identical_values(self) -> None:
        """Test numeric consistency with identical values."""
        values = [0.5, 0.5, 0.5]
        calc = ConsistencyCalculator()

        consistency = calc.numeric_consistency(values)
        assert consistency == 1.0

    def test_numeric_consistency_different_values(self) -> None:
        """Test numeric consistency with different values."""
        values = [0.1, 0.5, 0.9]
        calc = ConsistencyCalculator()

        consistency = calc.numeric_consistency(values)
        assert 0.0 <= consistency <= 1.0
        assert consistency < 1.0

    def test_numeric_consistency_insufficient_values(self) -> None:
        """Test numeric consistency with insufficient values."""
        values = [0.5]
        calc = ConsistencyCalculator()

        consistency = calc.numeric_consistency(values)
        assert consistency == 0.0

    def test_categorical_consensus_perfect(self) -> None:
        """Test categorical consensus with perfect agreement."""
        values = ["neutral", "neutral", "neutral"]
        calc = ConsistencyCalculator()

        consensus = calc.categorical_consensus(values)
        assert consensus == 1.0

    def test_categorical_consensus_mixed(self) -> None:
        """Test categorical consensus with mixed values."""
        values = ["neutral", "assertive", "neutral"]
        calc = ConsistencyCalculator()

        consensus = calc.categorical_consensus(values)
        assert 0.0 <= consensus <= 1.0
        assert consensus < 1.0

    def test_textual_consistency_identical(self) -> None:
        """Test textual consistency with identical texts."""
        values = ["This is a test", "This is a test", "This is a test"]
        calc = ConsistencyCalculator()

        consistency = calc.textual_consistency(values)
        assert consistency == 1.0

    def test_textual_consistency_different(self) -> None:
        """Test textual consistency with different texts."""
        values = ["This is a test", "Another statement", "Third phrase"]
        calc = ConsistencyCalculator()

        consistency = calc.textual_consistency(values)
        assert 0.0 <= consistency <= 1.0
        assert consistency < 1.0


class TestUncertaintyScorer:
    """Test uncertainty scoring functionality."""

    @pytest.fixture
    def mock_ai_backend(self) -> AsyncMock:
        """Mock AI backend for testing."""
        backend = AsyncMock()
        return backend

    @pytest.fixture
    def uncertainty_scorer(self, mock_ai_backend: AsyncMock) -> UncertaintyScorer:
        """Create uncertainty scorer with mock backend."""
        return UncertaintyScorer(mock_ai_backend)

    @pytest.mark.asyncio
    async def test_score_sentence_success(
        self, uncertainty_scorer: UncertaintyScorer, mock_ai_backend: AsyncMock
    ) -> None:
        """Test successful sentence scoring."""
        # Mock AI responses
        mock_responses = [
            '{"AI_Duygu_Skoru": 0.2, "AI_Risk_Skoru": 5}',
            '{"AI_Duygu_Skoru": 0.3, "AI_Risk_Skoru": 6}',
            '{"AI_Duygu_Skoru": 0.1, "AI_Risk_Skoru": 4}',
        ]
        mock_ai_backend.return_value = mock_responses

        result = await uncertainty_scorer.score_sentence(
            sent_id="test_001", source_text="Test sentence for scoring."
        )

        assert result.sent_id == "test_001"
        assert 0.0 <= result.overall_confidence <= 1.0
        assert result.recommendation in ["ACCEPT", "REVIEW", "REJECT"]
        assert len(result.field_scores) > 0
        assert len(result.consensus_map) > 0
        assert len(result.raw_outputs) == 3

    @pytest.mark.asyncio
    async def test_score_sentence_insufficient_outputs(
        self, uncertainty_scorer: UncertaintyScorer, mock_ai_backend: AsyncMock
    ) -> None:
        """Test scoring with insufficient AI outputs."""
        # Mock only one successful response
        mock_ai_backend.return_value = ['{"AI_Duygu_Skoru": 0.2}']

        result = await uncertainty_scorer.score_sentence(
            sent_id="test_002", source_text="Another test sentence."
        )

        assert result.sent_id == "test_002"
        assert result.overall_confidence == 0.0
        assert result.recommendation == "REJECT"

    @pytest.mark.asyncio
    async def test_score_batch(
        self, uncertainty_scorer: UncertaintyScorer, mock_ai_backend: AsyncMock
    ) -> None:
        """Test batch scoring."""
        # Mock AI responses
        mock_ai_backend.return_value = [
            '{"AI_Duygu_Skoru": 0.2, "AI_Risk_Skoru": 5}',
            '{"AI_Duygu_Skoru": 0.3, "AI_Risk_Skoru": 6}',
            '{"AI_Duygu_Skoru": 0.1, "AI_Risk_Skoru": 4}',
        ]

        sentences = [
            {"sent_id": "test_001", "text": "First sentence"},
            {"sent_id": "test_002", "text": "Second sentence"},
        ]

        results = await uncertainty_scorer.score_batch(sentences)

        assert len(results) == 2
        for result in results:
            assert result.sent_id in ["test_001", "test_002"]
            assert 0.0 <= result.overall_confidence <= 1.0

    def test_calculate_overall_confidence(
        self, uncertainty_scorer: UncertaintyScorer
    ) -> None:
        """Test overall confidence calculation."""
        field_scores = {
            "AI_Risk_Skoru": 0.8,
            "AI_Duygu_Skoru": 0.9,
            "AI_Cerceveleme": 0.7,
            "AI_Diplomatik_Ton": 0.6,
            "AI_Manipulasyon_Skor": 0.5,
        }

        confidence = uncertainty_scorer._calculate_overall_confidence(field_scores)

        assert 0.0 <= confidence <= 1.0
        # Risk score should have highest weight
        assert confidence > 0.5

    def test_get_consensus_values(self, uncertainty_scorer: UncertaintyScorer) -> None:
        """Test consensus value calculation."""
        outputs = [
            {"AI_Duygu_Skoru": 0.2, "AI_Risk_Skoru": 5, "tone": "neutral"},
            {"AI_Duygu_Skoru": 0.3, "AI_Risk_Skoru": 6, "tone": "neutral"},
            {"AI_Duygu_Skoru": 0.1, "AI_Risk_Skoru": 4, "tone": "assertive"},
        ]

        consensus = uncertainty_scorer._get_consensus_values(outputs)

        assert consensus["AI_Duygu_Skoru"] == "0.2"  # Most frequent
        assert consensus["tone"] == "neutral"  # Most frequent

    def test_make_recommendation_accept(
        self, uncertainty_scorer: UncertaintyScorer
    ) -> None:
        """Test ACCEPT recommendation."""
        result = uncertainty_scorer._make_recommendation(0.9, {"AI_Risk_Skoru": 0.8})
        assert result == "ACCEPT"

    def test_make_recommendation_review(
        self, uncertainty_scorer: UncertaintyScorer
    ) -> None:
        """Test REVIEW recommendation."""
        result = uncertainty_scorer._make_recommendation(0.7, {"AI_Risk_Skoru": 0.6})
        assert result == "REVIEW"

    def test_make_recommendation_reject(
        self, uncertainty_scorer: UncertaintyScorer
    ) -> None:
        """Test REJECT recommendation."""
        result = uncertainty_scorer._make_recommendation(0.4, {"AI_Risk_Skoru": 0.3})
        assert result == "REJECT"

    def test_field_type_detection(self, uncertainty_scorer: UncertaintyScorer) -> None:
        """Test field type detection."""
        assert uncertainty_scorer._is_numeric_field("AI_Risk_Skoru") is True
        assert uncertainty_scorer._is_numeric_field("AI_Duygu_Skoru") is True
        assert uncertainty_scorer._is_numeric_field("AI_Talep_Var") is True

        assert uncertainty_scorer._is_categorical_field("AI_Potansiyel_Risk") is True
        assert uncertainty_scorer._is_categorical_field("AI_Diplomatik_Ton") is True

        # Textual field
        assert uncertainty_scorer._is_numeric_field("AI_Birincil_Konu") is False
        assert uncertainty_scorer._is_categorical_field("AI_Birincil_Konu") is False

    def test_field_weights(self, uncertainty_scorer: UncertaintyScorer) -> None:
        """Test field weight assignment."""
        # Risk score should have highest weight
        risk_weight = uncertainty_scorer._get_field_weight("AI_Risk_Skoru")
        sentiment_weight = uncertainty_scorer._get_field_weight("AI_Duygu_Skoru")
        textual_weight = uncertainty_scorer._get_field_weight("AI_Birincil_Konu")

        assert risk_weight > sentiment_weight
        assert sentiment_weight > textual_weight
        assert risk_weight == 0.30
        assert sentiment_weight == 0.20
        assert textual_weight == 0.10


class TestUncertaintyIntegration:
    """Integration tests for uncertainty scoring."""

    @pytest.mark.asyncio
    async def test_end_to_end_scoring(self) -> None:
        """Test end-to-end uncertainty scoring workflow."""
        # Create mock backend
        mock_backend = AsyncMock()
        mock_backend.return_value = [
            '{"AI_Duygu_Skoru": 0.2, "AI_Risk_Skoru": 5, '
            '"AI_Potansiyel_Risk": "medium"}',
            '{"AI_Duygu_Skoru": 0.3, "AI_Risk_Skoru": 6, '
            '"AI_Potansiyel_Risk": "medium"}',
            '{"AI_Duygu_Skoru": 0.1, "AI_Risk_Skoru": 4, '
            '"AI_Potansiyel_Risk": "medium"}',
        ]

        scorer = UncertaintyScorer(mock_backend)

        # Test single sentence
        result = await scorer.score_sentence(
            sent_id="integration_test",
            source_text="This is an integration test sentence.",
        )

        assert result.sent_id == "integration_test"
        assert result.overall_confidence > 0.5  # Should be reasonably confident
        assert len(result.field_scores) > 0
        assert result.recommendation in ["ACCEPT", "REVIEW", "REJECT"]

        # Test batch
        sentences = [
            {"sent_id": "batch_001", "text": "First batch sentence"},
            {"sent_id": "batch_002", "text": "Second batch sentence"},
        ]

        batch_results = await scorer.score_batch(sentences)
        assert len(batch_results) == 2

        for result in batch_results:
            assert result.sent_id.startswith("batch_")
            assert 0.0 <= result.overall_confidence <= 1.0
