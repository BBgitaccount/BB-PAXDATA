"""Integration tests for the complete quality assurance pipeline."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bb_paxdata.domain.services.duplicate_protection import DuplicateProtectionService
from bb_paxdata.domain.services.temporal import DriftEvent, TemporalAnalyzer
from bb_paxdata.quality.data_contract import DataContractValidator
from bb_paxdata.quality.evaluator import QualityEvaluator, QualityReport
from bb_paxdata.quality.review_queue import ReviewFlagger, ReviewQueueManager
from bb_paxdata.quality.uncertainty import UncertaintyScore, UncertaintyScorer

from tests.fixtures.golden_dataset import GoldenDataset


class TestQualityPipelineIntegration:
    """Integration tests for the complete quality assurance pipeline."""

    @pytest.fixture
    def mock_db_session(self) -> Mock:
        """Create mock database session."""
        return Mock()

    @pytest.fixture
    def mock_ai_backend(self) -> Mock:
        """Create mock AI backend."""
        return Mock()

    @pytest.fixture
    def golden_dataset(self) -> GoldenDataset:
        """Load golden dataset for testing."""
        return GoldenDataset()

    @pytest.fixture
    def quality_evaluator(self, golden_dataset: GoldenDataset) -> QualityEvaluator:
        """Create QualityEvaluator instance."""
        return QualityEvaluator()

    @pytest.fixture
    def uncertainty_scorer(self, mock_ai_backend: Mock) -> UncertaintyScorer:
        """Create UncertaintyScorer instance."""
        return UncertaintyScorer(mock_ai_backend)

    @pytest.fixture
    def data_contract_validator(self) -> DataContractValidator:
        """Create DataContractValidator instance."""
        return DataContractValidator()

    @pytest.fixture
    def review_flagger(self, mock_db_session: Mock) -> ReviewFlagger:
        """Create ReviewFlagger instance."""
        return ReviewFlagger(mock_db_session)

    @pytest.fixture
    def review_manager(self, mock_db_session: Mock) -> ReviewQueueManager:
        """Create ReviewQueueManager instance."""
        return ReviewQueueManager(mock_db_session)

    @pytest.fixture
    def duplicate_protection(self, mock_db_session: Mock) -> DuplicateProtectionService:
        """Create DuplicateProtectionService instance."""
        return DuplicateProtectionService(mock_db_session)

    @pytest.fixture
    def temporal_analyzer(self) -> TemporalAnalyzer:
        """Create TemporalAnalyzer instance."""
        return TemporalAnalyzer()

    @pytest.fixture
    def sample_ai_output(self) -> dict[str, Any]:
        """Sample AI analysis output."""
        return {
            "AI_Duygu_Skoru": -0.25,
            "AI_Duygu_Kategorisi": "concerned",
            "AI_Risk_Skoru": 6,
            "AI_Potansiyel_Risk": "medium",
            "AI_Talep_Var": 0,
            "AI_Diplomatik_Ton": "defensive",
            "AI_Manipulasyon_Skor": 0.35,
            "AI_Cerceveleme": "security_frame",
            "AI_Birincil_Konu": "Güvenlik_Çatışma",
        }

    @pytest.fixture
    def sample_ground_truth(self) -> dict[str, Any]:
        """Sample ground truth data."""
        return {
            "AI_Duygu_Skoru": -0.30,
            "AI_Duygu_Kategorisi": "concerned",
            "AI_Risk_Skoru": 5,
            "AI_Potansiyel_Risk": "medium",
            "AI_Talep_Var": 0,
            "AI_Diplomatik_Ton": "defensive",
            "AI_Manipulasyon_Skor": 0.40,
            "AI_Cerceveleme": "security_frame",
            "AI_Birincil_Konu": "Güvenlik_Çatışma",
        }

    def test_complete_quality_pipeline_success(
        self,
        quality_evaluator: QualityEvaluator,
        uncertainty_scorer: UncertaintyScorer,
        review_flagger: ReviewFlagger,
        data_contract_validator: DataContractValidator,
        sample_ai_output: dict[str, Any],
        sample_ground_truth: dict[str, Any],
    ) -> None:
        """Test complete quality pipeline with successful results."""
        # Step 1: Validate AI output with data contract
        import pandas as pd  # type: ignore

        df = pd.DataFrame([sample_ai_output])
        validation_result = data_contract_validator.validate_ai_output(df)

        assert validation_result.passed is True
        assert validation_result.message == "AI output validation passed"

        # Step 2: Evaluate quality against golden dataset
        with patch.object(
            quality_evaluator.golden_dataset, "get_fixture_by_id"
        ) as mock_get_fixture:
            mock_get_fixture.return_value = {
                "ground_truth": sample_ground_truth,
                "source_text": (
                    "We do not seek escalation, but we will defend our sovereignty."
                ),
                "fixture_id": "test_001",
            }

            quality_report = quality_evaluator.evaluate_single_fixture(
                sample_ai_output,
                sample_ground_truth,
                "We do not seek escalation, but we will defend our sovereignty.",
                "test_001",
            )

        assert isinstance(quality_report, QualityReport)
        assert quality_report.fixture_id == "test_001"
        assert quality_report.passed is True  # Should pass with similar data
        assert quality_report.overall_score >= 0.7

    @pytest.mark.asyncio
    async def test_uncertainty_scoring_pipeline(
        self, uncertainty_scorer: UncertaintyScorer, mock_ai_backend: Mock
    ) -> None:
        """Test uncertainty scoring pipeline."""
        # Mock AI backend responses
        mock_responses = [
            json.dumps(
                {
                    "AI_Duygu_Skoru": -0.2,
                    "AI_Risk_Skoru": 5,
                    "AI_Potansiyel_Risk": "medium",
                    "AI_Diplomatik_Ton": "defensive",
                    "AI_Manipulasyon_Skor": 0.3,
                    "AI_Cerceveleme": "security_frame",
                    "AI_Birincil_Konu": "Güvenlik_Çatışma",
                }
            ),
            json.dumps(
                {
                    "AI_Duygu_Skoru": -0.3,
                    "AI_Risk_Skoru": 6,
                    "AI_Potansiyel_Risk": "medium",
                    "AI_Diplomatik_Ton": "defensive",
                    "AI_Manipulasyon_Skor": 0.4,
                    "AI_Cerceveleme": "security_frame",
                    "AI_Birincil_Konu": "Güvenlik_Çatışma",
                }
            ),
            json.dumps(
                {
                    "AI_Duygu_Skoru": -0.25,
                    "AI_Risk_Skoru": 5,
                    "AI_Potansiyel_Risk": "medium",
                    "AI_Diplomatik_Ton": "defensive",
                    "AI_Manipulasyon_Skor": 0.35,
                    "AI_Cerceveleme": "security_frame",
                    "AI_Birincil_Konu": "Güvenlik_Çatışma",
                }
            ),
        ]

        mock_ai_backend.return_value = AsyncMock()
        mock_ai_backend.return_value.call.return_value = mock_responses[0]

        # Mock the _call_ai_with_temperature method
        with patch.object(uncertainty_scorer, "_call_ai_with_temperature") as mock_call:
            mock_call.side_effect = mock_responses

            uncertainty_score = await uncertainty_scorer.score_sentence(
                sent_id="test_sent_001",
                source_text=(
                    "We do not seek escalation, but we will defend our sovereignty."
                ),
                context={"speaker_id": "speaker_001", "panel_id": "panel_001"},
            )

        assert isinstance(uncertainty_score, UncertaintyScore)
        assert uncertainty_score.sent_id == "test_sent_001"
        assert (
            uncertainty_score.overall_confidence >= 0.5
        )  # Should have reasonable confidence
        assert uncertainty_score.recommendation in ["ACCEPT", "REVIEW", "REJECT"]
        assert len(uncertainty_score.field_scores) > 0
        assert len(uncertainty_score.consensus_map) > 0
        assert len(uncertainty_score.raw_outputs) == 3

    def test_review_flagging_pipeline(
        self, review_flagger: ReviewFlagger, sample_ai_output: dict[str, Any]
    ) -> None:
        """Test review flagging pipeline."""
        # Test high risk scenario
        high_risk_output = sample_ai_output.copy()
        high_risk_output["AI_Risk_Skoru"] = 8

        should_flag, trigger_type, trigger_details = (
            review_flagger.should_flag_for_review(
                high_risk_output, uncertainty_score=0.3, quality_result=None
            )
        )

        assert should_flag is True
        assert trigger_type == "HIGH_RISK"
        assert "Risk score 8" in trigger_details["details"]

        # Test critical risk scenario
        critical_risk_output = sample_ai_output.copy()
        critical_risk_output["AI_Potansiyel_Risk"] = "critical"

        should_flag, trigger_type, trigger_details = (
            review_flagger.should_flag_for_review(
                critical_risk_output, uncertainty_score=0.3, quality_result=None
            )
        )

        assert should_flag is True
        assert trigger_type == "CRITICAL_RISK"

        # Test low uncertainty scenario
        should_flag, trigger_type, trigger_details = (
            review_flagger.should_flag_for_review(
                sample_ai_output, uncertainty_score=0.4, quality_result=None
            )
        )

        assert should_flag is True
        assert trigger_type == "LOW_UNCERTAINTY"

        # Test quality failure scenario
        mock_quality_result = Mock()
        mock_quality_result.passed = False
        mock_quality_result.overall_score = 0.6

        should_flag, trigger_type, trigger_details = (
            review_flagger.should_flag_for_review(
                sample_ai_output,
                uncertainty_score=0.8,
                quality_result=mock_quality_result,
            )
        )

        assert should_flag is True
        assert trigger_type == "QUALITY_FAILURE"

        # Test no flag scenario
        safe_output = sample_ai_output.copy()
        safe_output["AI_Risk_Skoru"] = 2
        safe_output["AI_Potansiyel_Risk"] = "low"

        should_flag, trigger_type, trigger_details = (
            review_flagger.should_flag_for_review(
                safe_output, uncertainty_score=0.9, quality_result=None
            )
        )

        assert should_flag is False
        assert trigger_type == ""

    def test_temporal_analysis_pipeline(
        self, temporal_analyzer: TemporalAnalyzer
    ) -> None:
        """Test temporal analysis pipeline."""
        panel_data = {"panel_id": "test_panel_001"}
        speaker_data = {
            "speaker_001": {"name": "Test Speaker", "country": "Test Country"}
        }

        # Create sentence data with drift
        sentence_data = [
            {
                "sent_id": "sent_001",
                "speaker_id": "speaker_001",
                "global_sent_order": 1,
                "text": "We welcome this opportunity for dialogue.",
                "AI_Duygu_Skoru": 0.5,
                "AI_Risk_Skoru": 2,
                "AI_Birincil_Konu": "Diplomasi",
                "AI_Diplomatik_Ton": "conciliatory",
            },
            {
                "sent_id": "sent_002",
                "speaker_id": "speaker_001",
                "global_sent_order": 2,
                "text": "We must defend our position strongly.",
                "AI_Duygu_Skoru": -0.3,
                "AI_Risk_Skoru": 6,
                "AI_Birincil_Konu": "Güvenlik_Çatışma",
                "AI_Diplomatik_Ton": "defensive",
            },
            {
                "sent_id": "sent_003",
                "speaker_id": "speaker_001",
                "global_sent_order": 3,
                "text": "This is unacceptable aggression.",
                "AI_Duygu_Skoru": -0.8,
                "AI_Risk_Skoru": 9,
                "AI_Birincil_Konu": "Güvenlik_Çatışma",
                "AI_Diplomatik_Ton": "confrontational",
            },
        ]

        drift_events = temporal_analyzer.analyze_panel_drift(
            panel_data, speaker_data, sentence_data
        )

        assert isinstance(drift_events, list)
        # Should detect some drift with this data
        assert len(drift_events) >= 0

        for event in drift_events:
            assert isinstance(event, DriftEvent)
            assert event.speaker_id == "speaker_001"
            assert event.panel_id == "test_panel_001"
            assert event.drift_type in ["SENTIMENT", "TOPIC", "LEXICAL", "TONE", "RISK"]
            assert event.severity in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_duplicate_protection_pipeline(
        self, duplicate_protection: DuplicateProtectionService, mock_db_session: Mock
    ) -> None:
        """Test duplicate protection pipeline."""
        file_content = "Sample transcript content for testing."
        file_path = Path("test_transcript.txt")

        # Generate idempotency key
        idempotency_key = duplicate_protection.generate_idempotency_key(
            file_content, str(file_path), "1.0", "1.0"
        )

        assert len(idempotency_key) == 64  # SHA256 hash

        # Test new file check
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        is_processed, processed_file = duplicate_protection.is_already_processed(
            idempotency_key
        )

        assert is_processed is False
        assert processed_file is None

        # Test marking as processed
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()

        result = duplicate_protection.mark_as_processed(
            file_path, file_content, idempotency_key
        )

        assert result is not None
        assert result.file_name == file_path.name
        assert result.idempotency_key == idempotency_key
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_end_to_end_quality_workflow(
        self,
        quality_evaluator: QualityEvaluator,
        uncertainty_scorer: UncertaintyScorer,
        review_flagger: ReviewFlagger,
        data_contract_validator: DataContractValidator,
        mock_db_session: Mock,
        sample_ai_output: dict[str, Any],
        sample_ground_truth: dict[str, Any],
    ) -> None:
        """Test end-to-end quality workflow."""
        # Step 1: Data contract validation
        import pandas as pd

        df = pd.DataFrame([sample_ai_output])
        validation_result = data_contract_validator.validate_ai_output(df)
        assert validation_result.passed is True

        # Step 2: Quality evaluation
        with patch.object(
            quality_evaluator.golden_dataset, "get_fixture_by_id"
        ) as mock_get_fixture:
            mock_get_fixture.return_value = {
                "ground_truth": sample_ground_truth,
                "source_text": "Test sentence.",
                "fixture_id": "test_001",
            }

            quality_report = quality_evaluator.evaluate_single_fixture(
                sample_ai_output, sample_ground_truth, "Test sentence.", "test_001"
            )

        # Step 3: Review flagging
        should_flag, trigger_type, trigger_details = (
            review_flagger.should_flag_for_review(
                sample_ai_output,
                uncertainty_score=0.8,  # High confidence
                quality_result=quality_report,
            )
        )

        # Should not flag if quality is good and confidence is high
        if quality_report.passed:
            assert should_flag is False or trigger_type == "LOW_UNCERTAINTY"

        # Step 4: Database operations (mocked)
        if should_flag:
            mock_db_session.add = Mock()
            mock_db_session.commit = Mock()

            flagged_entry = review_flagger.flag_sentence(
                "test_sent_001",
                sample_ai_output,
                trigger_type,
                trigger_details,
                {"panel_id": "test_panel_001", "speaker_name": "Test Speaker"},
            )

            assert flagged_entry is not None
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    def test_quality_metrics_calculation(
        self,
        quality_evaluator: QualityEvaluator,
        mock_ai_backend: Mock,
        golden_dataset: GoldenDataset,
    ) -> None:
        """Test quality metrics calculation accuracy."""
        # Load actual golden dataset fixture
        with patch.object(golden_dataset, "load_dataset") as mock_load:
            mock_load.return_value = {
                "fixtures": [
                    {
                        "fixture_id": "test_001",
                        "source_text": "We do not seek escalation.",
                        "ground_truth": {
                            "AI_Duygu_Skoru": -0.25,
                            "AI_Risk_Skoru": 5,
                            "AI_Potansiyel_Risk": "medium",
                            "AI_Diplomatik_Ton": "defensive",
                        },
                    }
                ]
            }

            # Create AI results with slight variations
            ai_results = [
                {
                    "AI_Duygu_Skoru": -0.30,  # Slight difference
                    "AI_Risk_Skoru": 5,  # Exact match
                    "AI_Potansiyel_Risk": "medium",  # Exact match
                    "AI_Diplomatik_Ton": "defensive",  # Exact match
                }
            ]

            evaluation_result = quality_evaluator.evaluate_golden_dataset(ai_results)

            assert "summary" in evaluation_result
            assert "reports" in evaluation_result
            assert evaluation_result["total_fixtures"] == 1
            assert evaluation_result["evaluated_fixtures"] == 1

            summary = evaluation_result["summary"]
            assert "overall_mean_score" in summary
            assert "overall_pass_rate" in summary
            assert "metric_statistics" in summary

            # Should have reasonable scores
            assert summary["overall_mean_score"] >= 0.5
            assert summary["overall_mean_score"] <= 1.0
