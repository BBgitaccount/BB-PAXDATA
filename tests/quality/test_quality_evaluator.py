"""Tests for QualityEvaluator."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from bb_paxdata.quality.evaluator import (
    EvaluationResult,
    QualityEvaluator,
    QualityReport,
)
from bb_paxdata.tests.fixtures.golden_dataset import GoldenDataset  # type: ignore


class TestQualityEvaluator:
    """Test QualityEvaluator functionality."""

    @pytest.fixture
    def evaluator(self) -> QualityEvaluator:
        """Create QualityEvaluator instance for testing."""
        return QualityEvaluator(model_name="test-model", backend_used="test-backend")

    @pytest.fixture
    def sample_ground_truth(self) -> dict[str, Any]:
        """Sample ground truth data."""
        return {
            "AI_Duygu_Skoru": 0.2,
            "AI_Risk_Skoru": 5,
            "AI_Potansiyel_Risk": "medium",
            "AI_Diplomatik_Ton": "neutral",
            "AI_Manipulasyon_Skor": 0.3,
            "AI_Talep_Var": 0,
            "AI_Birincil_Konu": "Ekonomi",
        }

    @pytest.fixture
    def sample_ai_output(self) -> dict[str, Any]:
        """Sample AI output data."""
        return {
            "AI_Duygu_Skoru": 0.3,
            "AI_Risk_Skoru": 6,
            "AI_Potansiyel_Risk": "high",
            "AI_Diplomatik_Ton": "assertive",
            "AI_Manipulasyon_Skor": 0.4,
            "AI_Talep_Var": 1,
            "AI_Birincil_Konu": "Güvenlik",
        }

    def test_evaluator_initialization(self, evaluator: QualityEvaluator) -> None:
        """Test evaluator initialization."""
        assert evaluator.model_name == "test-model"
        assert evaluator.backend_used == "test-backend"
        assert evaluator.golden_dataset is not None
        assert len(evaluator.custom_metrics) == 3
        assert len(evaluator.deepeval_metrics) == 3

    def test_evaluate_single_fixture_perfect_match(
        self,
        evaluator: QualityEvaluator,
        sample_ai_output: dict[str, Any],
        sample_ground_truth: dict[str, Any],
    ) -> None:
        """Test evaluation with perfect AI-ground truth match."""
        # Create perfect match
        perfect_ai_output = sample_ground_truth.copy()

        report = evaluator.evaluate_single_fixture(
            ai_output=perfect_ai_output,
            ground_truth=sample_ground_truth,
            source_text="Test sentence.",
            fixture_id="test_001",
        )

        assert report.fixture_id == "test_001"
        assert report.model_used == "test-model"
        assert report.backend_used == "test-backend"
        assert report.overall_score >= 0.9  # Should be very high
        assert report.passed is True
        assert len(report.details) > 0

    def test_evaluate_single_fixture_poor_match(
        self,
        evaluator: QualityEvaluator,
        sample_ai_output: dict[str, Any],
        sample_ground_truth: dict[str, Any],
    ) -> None:
        """Test evaluation with poor AI-ground truth match."""
        # Create poor match
        poor_ai_output = {
            "AI_Duygu_Skoru": -0.8,  # Very different
            "AI_Risk_Skoru": 10,  # Very different
            "AI_Potansiyel_Risk": "critical",  # Different
            "AI_Diplomatik_Ton": "confrontational",  # Different
            "AI_Manipulasyon_Skor": 0.9,  # Very different
            "AI_Talep_Var": 1,
            "AI_Birincil_Konu": "Savaş",  # Different
        }

        report = evaluator.evaluate_single_fixture(
            ai_output=poor_ai_output,
            ground_truth=sample_ground_truth,
            source_text="Test sentence.",
            fixture_id="test_002",
        )

        assert report.fixture_id == "test_002"
        assert report.overall_score < 0.5  # Should be low
        assert report.passed is False
        assert len(report.details) > 0

    def test_evaluate_single_fixture_missing_fields(
        self, evaluator: QualityEvaluator
    ) -> None:
        """Test evaluation with missing fields."""
        incomplete_ai_output = {
            "AI_Duygu_Skoru": 0.2
            # Missing other required fields
        }

        ground_truth = {"AI_Duygu_Skoru": 0.2, "AI_Risk_Skoru": 5}

        report = evaluator.evaluate_single_fixture(
            ai_output=incomplete_ai_output,
            ground_truth=ground_truth,
            source_text="Test sentence.",
            fixture_id="test_003",
        )

        assert report.fixture_id == "test_003"
        assert report.overall_score < 0.5  # Should be low due to missing fields
        assert len(report.details) > 0

    def test_calculate_overall_score(self, evaluator: QualityEvaluator) -> None:
        """Test overall score calculation."""
        evaluation_results = [
            EvaluationResult(
                metric_name="sentiment_agreement",
                score=0.9,
                threshold=0.8,
                passed=True,
                reason="Good match",
                latency_ms=100,
            ),
            EvaluationResult(
                metric_name="risk_calibration",
                score=0.8,
                threshold=0.7,
                passed=True,
                reason="Good calibration",
                latency_ms=150,
            ),
            EvaluationResult(
                metric_name="topic_accuracy",
                score=0.7,
                threshold=0.85,
                passed=False,
                reason="Topic mismatch",
                latency_ms=120,
            ),
        ]

        overall_score = evaluator._calculate_overall_score(evaluation_results)

        assert 0.0 <= overall_score <= 1.0
        # Should be weighted average
        assert 0.7 <= overall_score <= 0.9

    @patch("bb_paxdata.quality.evaluator.evaluate")
    def test_evaluate_batch_success(
        self, mock_evaluate: MagicMock, evaluator: QualityEvaluator
    ) -> None:
        """Test successful batch evaluation."""
        # Mock deepeval evaluate function
        mock_evaluate.return_value = None

        ai_results = [
            {"AI_Duygu_Skoru": 0.2, "AI_Risk_Skoru": 5},
            {"AI_Duygu_Skoru": 0.3, "AI_Risk_Skoru": 6},
        ]
        source_texts = ["First sentence.", "Second sentence."]
        fixture_ids = ["test_001", "test_002"]

        # Mock golden dataset
        evaluator.golden_dataset.get_fixture_by_id = MagicMock(
            return_value={"ground_truth": {"AI_Duygu_Skoru": 0.2, "AI_Risk_Skoru": 5}}
        )

        reports = evaluator.evaluate_batch(ai_results, source_texts, fixture_ids)

        assert len(reports) == 2
        for report in reports:
            assert isinstance(report, QualityReport)
            assert report.fixture_id in fixture_ids

    def test_evaluate_batch_mismatched_lengths(
        self, evaluator: QualityEvaluator
    ) -> None:
        """Test batch evaluation with mismatched input lengths."""
        ai_results = [{"AI_Duygu_Skoru": 0.2}]
        source_texts = ["First sentence.", "Second sentence."]
        fixture_ids = ["test_001"]

        with pytest.raises(ValueError, match="must have same length"):
            evaluator.evaluate_batch(ai_results, source_texts, fixture_ids)

    def test_evaluate_golden_dataset_success(self, evaluator: QualityEvaluator) -> None:
        """Test evaluation against golden dataset."""
        # Mock golden dataset
        mock_dataset = {
            "fixtures": [
                {
                    "fixture_id": "gd_001",
                    "source_text": "First test sentence.",
                    "ground_truth": {"AI_Duygu_Skoru": 0.2, "AI_Risk_Skoru": 5},
                },
                {
                    "fixture_id": "gd_002",
                    "source_text": "Second test sentence.",
                    "ground_truth": {"AI_Duygu_Skoru": 0.3, "AI_Risk_Skoru": 6},
                },
            ]
        }

        evaluator.golden_dataset.load_dataset = MagicMock(return_value=mock_dataset)

        ai_results = [
            {"AI_Duygu_Skoru": 0.2, "AI_Risk_Skoru": 5},
            {"AI_Duygu_Skoru": 0.3, "AI_Risk_Skoru": 6},
        ]

        with patch("bb_paxdata.quality.evaluator.evaluate") as mock_evaluate:
            mock_evaluate.return_value = None

            result = evaluator.evaluate_golden_dataset(ai_results)

            assert "summary" in result
            assert "reports" in result
            assert result["total_fixtures"] == 2
            assert result["evaluated_fixtures"] == 2
            assert result["model_used"] == "test-model"

    def test_calculate_summary_statistics(self, evaluator: QualityEvaluator) -> None:
        """Test summary statistics calculation."""
        reports = [
            QualityReport(
                fixture_id="test_001",
                overall_score=0.9,
                passed=True,
                details=[
                    EvaluationResult(
                        metric_name="sentiment_agreement",
                        score=0.9,
                        threshold=0.8,
                        passed=True,
                        reason="Good",
                        latency_ms=100,
                    )
                ],
                model_used="test-model",
                backend_used="test-backend",
                evaluated_at=datetime.now(timezone.utc),
            ),
            QualityReport(
                fixture_id="test_002",
                overall_score=0.6,
                passed=False,
                details=[
                    EvaluationResult(
                        metric_name="risk_calibration",
                        score=0.6,
                        threshold=0.7,
                        passed=False,
                        reason="Poor",
                        latency_ms=150,
                    )
                ],
                model_used="test-model",
                backend_used="test-backend",
                evaluated_at=datetime.now(timezone.utc),
            ),
        ]

        stats = evaluator._calculate_summary_statistics(reports)

        assert stats["overall_mean_score"] == 0.75  # (0.9 + 0.6) / 2
        assert stats["overall_min_score"] == 0.6
        assert stats["overall_max_score"] == 0.9
        assert stats["overall_pass_rate"] == 0.5  # 1 out of 2 passed
        assert stats["total_reports"] == 2
        assert "metric_statistics" in stats


class TestCustomMetrics:
    """Test custom quality metrics."""

    def test_sentiment_agreement_metric_perfect(self) -> None:
        """Test sentiment agreement with perfect match."""
        from bb_paxdata.quality.metrics.custom.sentiment_agreement import (
            SentimentAgreementMetric,
        )

        metric = SentimentAgreementMetric()

        ai_output = {"AI_Duygu_Skoru": 0.2}
        ground_truth = {"AI_Duygu_Skoru": 0.2}

        result = metric.measure(ai_output, ground_truth)

        assert result.score == 1.0
        assert result.passed is True
        assert result.reason is not None
        assert "perfect" in result.reason.lower()

    def test_sentiment_agreement_metric_poor(self) -> None:
        """Test sentiment agreement with poor match."""
        from bb_paxdata.quality.metrics.custom.sentiment_agreement import (
            SentimentAgreementMetric,
        )

        metric = SentimentAgreementMetric()

        ai_output = {"AI_Duygu_Skoru": 0.8}
        ground_truth = {"AI_Duygu_Skoru": -0.8}

        result = metric.measure(ai_output, ground_truth)

        assert result.score < 0.5
        assert result.passed is False

    def test_risk_calibration_metric_perfect(self) -> None:
        """Test risk calibration with perfect match."""
        from bb_paxdata.quality.metrics.custom.risk_calibration import (
            RiskCalibrationMetric,
        )

        metric = RiskCalibrationMetric()

        ai_output = {"AI_Risk_Skoru": 5, "AI_Potansiyel_Risk": "medium"}
        ground_truth = {"AI_Risk_Skoru": 5, "AI_Potansiyel_Risk": "medium"}

        result = metric.measure(ai_output, ground_truth)

        assert result.score >= 0.9
        assert result.passed is True

    def test_topic_accuracy_metric_exact_match(self) -> None:
        """Test topic accuracy with exact match."""
        from bb_paxdata.quality.metrics.custom.topic_accuracy import TopicAccuracyMetric

        metric = TopicAccuracyMetric()

        ai_output = {"AI_Birincil_Konu": "Güvenlik_Çatışma"}
        ground_truth = {"AI_Birincil_Konu": "Güvenlik_Çatışma"}

        result = metric.measure(ai_output, ground_truth)

        assert result.score == 1.0
        assert result.passed is True
        assert result.reason is not None
        assert "exact" in result.reason.lower()

    def test_topic_accuracy_metric_partial_match(self) -> None:
        """Test topic accuracy with partial match."""
        from bb_paxdata.quality.metrics.custom.topic_accuracy import TopicAccuracyMetric

        metric = TopicAccuracyMetric()

        ai_output = {"AI_Birincil_Konu": "security conflict"}
        ground_truth = {"AI_Birincil_Konu": "Güvenlik_Çatışma"}

        result = metric.measure(ai_output, ground_truth)

        assert 0.7 <= result.score < 1.0
        assert result.reason is not None
        assert "partial" in result.reason.lower()


class TestQualityIntegration:
    """Integration tests for quality evaluation."""

    @pytest.mark.asyncio
    async def test_end_to_end_evaluation(self) -> None:
        """Test end-to-end quality evaluation workflow."""
        # Create test dataset
        test_dataset = {
            "version": "1.0",
            "created_at": "2026-05-12",
            "fixtures": [
                {
                    "fixture_id": "test_001",
                    "sent_id": "sent_001",
                    "source_text": "This is a test sentence.",
                    "ground_truth": {
                        "AI_Duygu_Skoru": 0.2,
                        "AI_Risk_Skoru": 3,
                        "AI_Potansiyel_Risk": "low",
                        "AI_Diplomatik_Ton": "neutral",
                        "AI_Manipulasyon_Skor": 0.1,
                        "AI_Talep_Var": 0,
                    },
                    "metadata": {
                        "why_selected": "representative_sample",
                        "annotator": "test",
                        "annotated_at": "2026-05-12",
                        "version": "1.0",
                    },
                }
            ],
        }

        # Mock golden dataset
        with patch.object(GoldenDataset, "load_dataset", return_value=test_dataset):
            evaluator = QualityEvaluator(model_name="test-model")

            ai_results = [
                {
                    "AI_Duygu_Skoru": 0.3,
                    "AI_Risk_Skoru": 4,
                    "AI_Potansiyel_Risk": "medium",
                }
            ]

            with patch("bb_paxdata.quality.evaluator.evaluate") as mock_evaluate:
                mock_evaluate.return_value = None

                result = evaluator.evaluate_golden_dataset(ai_results)

                assert "summary" in result
                assert "reports" in result
                assert result["total_fixtures"] == 1
                assert result["evaluated_fixtures"] == 1
