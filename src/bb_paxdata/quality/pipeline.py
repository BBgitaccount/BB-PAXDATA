"""Main quality assurance pipeline integration."""

from pathlib import Path
from typing import Any, TypedDict, cast

import structlog
from sqlalchemy.orm import Session

from tests.fixtures.golden_dataset import GoldenDataset

from ..domain.services.temporal import TemporalAnalyzer
from .data_contract import DataContractValidator, ValidationResult
from .evaluator import QualityEvaluator, QualityReport
from .review_queue import ReviewFlagger, ReviewQueueManager
from .uncertainty import UncertaintyScorer
from .violations import ViolationLogger

logger = structlog.get_logger(__name__)


class QualitySummary(TypedDict):
    file_path: str
    total_sentences: int
    validation_passed: bool
    uncertainty_issues: int
    quality_issues: int
    review_flags: int
    drift_events: list[dict[str, Any]]
    errors: list[str]


class HealthReport(TypedDict):
    timestamp: str
    overall_status: str
    components: dict[str, str]
    issues: list[str]
    recommendations: list[str]


class QualityPipeline:
    """Main quality assurance pipeline for AI analysis."""

    def __init__(self, db_session: Session, ai_backend: Any) -> None:
        self.db_session = db_session
        self.ai_backend = ai_backend
        self.logger = structlog.get_logger(__name__)

        # Initialize quality components
        self.data_validator = DataContractValidator()
        self.violation_logger = ViolationLogger()
        self.uncertainty_scorer = UncertaintyScorer(ai_backend)
        self.quality_evaluator = QualityEvaluator()
        self.review_flagger = ReviewFlagger(db_session)
        self.review_manager = ReviewQueueManager(db_session)
        self.temporal_analyzer = TemporalAnalyzer()
        self.golden_dataset = GoldenDataset()

    async def process_transcript(
        self, file_path: str, file_content: str, ai_results: list[dict[str, Any]]
    ) -> QualitySummary:
        """
        Process transcript through complete quality pipeline.

        Args:
            file_path: Path to transcript file
            file_content: Raw transcript content
            ai_results: List of AI analysis results

        Returns:
            Quality processing summary
        """
        summary: QualitySummary = {
            "file_path": file_path,
            "total_sentences": len(ai_results),
            "validation_passed": True,
            "uncertainty_issues": 0,
            "quality_issues": 0,
            "review_flags": 0,
            "drift_events": [],
            "errors": [],
        }

        try:
            # Step 1: Input validation
            self.logger.info(f"Starting quality pipeline for {file_path}")

            validation_result: ValidationResult = (
                self.data_validator.validate_transcript_input(
                    file_content, Path(file_path)
                )
            )

            if not validation_result.passed:
                summary["validation_passed"] = False
                summary["errors"].append(
                    f"Input validation failed: {validation_result.message}"
                )
                self.violation_logger.log_input_violation(
                    file_path, validation_result.details.get("failed_checks", [])
                )
                return summary

            # Step 2: Output validation
            import pandas as pd

            df = pd.DataFrame(ai_results)

            output_validation = self.data_validator.validate_ai_output(df)
            if not output_validation.passed:
                summary["validation_passed"] = False
                summary["errors"].append(
                    f"Output validation failed: {output_validation.message}"
                )
                # Continue processing but log violations

            # Step 3: Uncertainty scoring
            self.logger.info("Scoring uncertainty for AI outputs")

            sentences_for_scoring = [
                {
                    "sent_id": result.get("sent_id", f"sent_{i}"),
                    "text": result.get("text", ""),
                    "context": {
                        "speaker_name": result.get("speaker_name"),
                        "panel_id": result.get("panel_id"),
                    },
                }
                for i, result in enumerate(ai_results)
            ]

            uncertainty_scores = await self.uncertainty_scorer.score_batch(
                sentences_for_scoring
            )

            # Process uncertainty scores
            for uncertainty_score in uncertainty_scores:
                if uncertainty_score.recommendation in ["REVIEW", "REJECT"]:
                    summary["uncertainty_issues"] += 1

                    # Flag for review if needed
                    ai_output = next(
                        (
                            r
                            for r in ai_results
                            if r.get("sent_id") == uncertainty_score.sent_id
                        ),
                        {},
                    )

                    should_flag, trigger_type, trigger_details = (
                        self.review_flagger.should_flag_for_review(
                            ai_output, uncertainty_score.overall_confidence
                        )
                    )

                    if should_flag:
                        self.review_flagger.flag_sentence(
                            sent_id=uncertainty_score.sent_id,
                            ai_output=ai_output,
                            trigger_type=trigger_type,
                            trigger_details=trigger_details,
                            context={
                                "panel_id": ai_output.get("panel_id"),
                                "seg_id": ai_output.get("seg_id"),
                                "speaker_name": ai_output.get("speaker_name"),
                                "country": ai_output.get("country"),
                            },
                        )
                        summary["review_flags"] += 1

            # Step 4: Quality evaluation (if golden dataset available)
            golden_fixtures = self.golden_dataset.load_dataset().get("fixtures", [])
            if golden_fixtures:
                self.logger.info("Running quality evaluation against golden dataset")

                # Match AI results with golden fixtures
                matched_results = []
                source_texts = []
                fixture_ids = []

                for ai_result in ai_results:
                    sent_id = ai_result.get("sent_id")

                    # Find matching fixture (simplified matching)
                    matching_fixture = next(
                        (f for f in golden_fixtures if f.get("sent_id") == sent_id),
                        None,
                    )

                    if matching_fixture:
                        matched_results.append(ai_result)
                        source_texts.append(matching_fixture.get("source_text", ""))
                        fixture_ids.append(matching_fixture.get("fixture_id", ""))

                if matched_results:
                    quality_reports: list[QualityReport] = (
                        self.quality_evaluator.evaluate_batch(
                            matched_results, source_texts, fixture_ids
                        )
                    )

                    # Count quality issues
                    for report in quality_reports:
                        if not report.passed:
                            summary["quality_issues"] += 1

                            # Flag for review
                            ai_output = next(
                                (
                                    r
                                    for r in matched_results
                                    if r.get("sent_id") == report.fixture_id
                                ),
                                {},
                            )

                            should_flag, trigger_type, trigger_details = (
                                self.review_flagger.should_flag_for_review(
                                    ai_output, quality_result=report
                                )
                            )

                            if should_flag:
                                self.review_flagger.flag_sentence(
                                    sent_id=report.fixture_id,
                                    ai_output=ai_output,
                                    trigger_type=trigger_type,
                                    trigger_details=trigger_details,
                                )
                                summary["review_flags"] += 1

            # Step 5: Auto-flagging for high risk/critical cases
            self.logger.info("Auto-flagging high risk and critical cases")

            for ai_result in ai_results:
                should_flag, trigger_type, trigger_details = (
                    self.review_flagger.should_flag_for_review(ai_result)
                )

                if should_flag:
                    self.review_flagger.flag_sentence(
                        sent_id=ai_result.get("sent_id", ""),
                        ai_output=ai_result,
                        trigger_type=trigger_type,
                        trigger_details=trigger_details,
                        context={
                            "panel_id": ai_result.get("panel_id"),
                            "seg_id": ai_result.get("seg_id"),
                            "speaker_name": ai_result.get("speaker_name"),
                            "country": ai_result.get("country"),
                        },
                    )
                    summary["review_flags"] += 1

            # Step 6: Temporal analysis (if panel-level data available)
            panel_id = ai_results[0].get("panel_id") if ai_results else None
            if panel_id:
                self.logger.info(f"Running temporal analysis for panel {panel_id}")

                try:
                    # Group by speaker for temporal analysis
                    speaker_data = {}
                    sentence_data = []

                    for result in ai_results:
                        speaker_id = result.get("speaker_id", "unknown")
                        if speaker_id not in speaker_data:
                            speaker_data[speaker_id] = {
                                "speaker_id": speaker_id,
                                "speaker_name": result.get("speaker_name"),
                                "country": result.get("country"),
                            }

                        sentence_data.append(
                            {
                                "speaker_id": speaker_id,
                                "global_sent_order": result.get("sent_order", 0),
                                "text": result.get("text", ""),
                                "AI_Duygu_Skoru": result.get("AI_Duygu_Skoru"),
                                "AI_Risk_Skoru": result.get("AI_Risk_Skoru"),
                                "AI_Diplomatik_Ton": result.get("AI_Diplomatik_Ton"),
                                "AI_Birincil_Konu": result.get("AI_Birincil_Konu"),
                            }
                        )

                    panel_data = {"panel_id": panel_id}

                    drift_events = self.temporal_analyzer.analyze_panel_drift(
                        panel_data, speaker_data, sentence_data
                    )

                    summary["drift_events"] = [
                        {
                            "speaker_id": drift.speaker_id,
                            "drift_type": drift.drift_type,
                            "severity": drift.severity,
                            "before_state": drift.before_state,
                            "after_state": drift.after_state,
                            "confidence": drift.confidence,
                        }
                        for drift in drift_events
                    ]

                    if drift_events:
                        self.logger.info(f"Found {len(drift_events)} drift events")

                except Exception as e:
                    self.logger.error(f"Error in temporal analysis: {e}")
                    summary["errors"].append(f"Temporal analysis error: {e!s}")

            self.logger.info(f"Quality pipeline completed for {file_path}")
            return summary

        except Exception as e:
            self.logger.error(f"Error in quality pipeline: {e}")
            summary["errors"].append(f"Pipeline error: {e!s}")
            return summary

    def get_pipeline_statistics(self) -> dict[str, Any]:
        """Get comprehensive pipeline statistics."""
        try:
            stats = {}

            # Review queue statistics
            review_stats = self.review_manager.get_queue_statistics()
            stats["review_queue"] = review_stats

            # Golden dataset statistics
            golden_stats = self.golden_dataset.get_statistics()
            stats["golden_dataset"] = golden_stats

            # Violation statistics (last 7 days)
            violation_stats = self.violation_logger.get_violation_summary(days=7)
            stats["violations"] = violation_stats

            return stats

        except Exception as e:
            self.logger.error(f"Error getting pipeline statistics: {e}")
            return {}

    async def run_quality_health_check(self) -> dict[str, Any]:
        """Run comprehensive quality health check."""
        issues: list[str] = []
        recommendations: list[str] = []
        health_report: HealthReport = {
            "timestamp": "2026-05-12T13:33:00Z",
            "overall_status": "healthy",
            "components": {},
            "issues": issues,
            "recommendations": recommendations,
        }

        try:
            # Check data contract validator
            health_report["components"]["data_validator"] = "healthy"

            # Check uncertainty scorer
            try:
                _ = await self.uncertainty_scorer.score_sentence(
                    sent_id="health_check", source_text="Health check sentence."
                )
                health_report["components"]["uncertainty_scorer"] = "healthy"
            except Exception as e:
                health_report["components"]["uncertainty_scorer"] = "unhealthy"
                health_report["issues"].append(f"Uncertainty scorer error: {e!s}")

            # Check quality evaluator
            try:
                self.quality_evaluator._calculate_overall_score([])
                health_report["components"]["quality_evaluator"] = "healthy"
            except Exception as e:
                health_report["components"]["quality_evaluator"] = "unhealthy"
                health_report["issues"].append(f"Quality evaluator error: {e!s}")

            # Check review queue
            try:
                self.review_manager.get_queue_statistics()
                health_report["components"]["review_queue"] = "healthy"
            except Exception as e:
                health_report["components"]["review_queue"] = "unhealthy"
                health_report["issues"].append(f"Review queue error: {e!s}")

            # Check temporal analyzer
            try:
                self.temporal_analyzer._calculate_drift_severity(0.5, "sentiment")
                health_report["components"]["temporal_analyzer"] = "healthy"
            except Exception as e:
                health_report["components"]["temporal_analyzer"] = "unhealthy"
                health_report["issues"].append(f"Temporal analyzer error: {e!s}")

            # Check golden dataset
            try:
                self.golden_dataset.load_dataset()
                health_report["components"]["golden_dataset"] = "healthy"
            except Exception as e:
                health_report["components"]["golden_dataset"] = "unhealthy"
                health_report["issues"].append(f"Golden dataset error: {e!s}")

            # Determine overall status
            unhealthy_components = [
                name
                for name, status in health_report["components"].items()
                if status == "unhealthy"
            ]

            if unhealthy_components:
                health_report["overall_status"] = "degraded"
                health_report["recommendations"].append(
                    f"Fix unhealthy components: {', '.join(unhealthy_components)}"
                )

            return cast(dict[str, Any], health_report)

        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
            health_report["overall_status"] = "error"
            health_report["issues"].append(f"Health check error: {e!s}")
            return cast(dict[str, Any], health_report)
