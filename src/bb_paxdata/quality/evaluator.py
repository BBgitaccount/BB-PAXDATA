"""Quality evaluator for AI analysis outputs using Deepeval and custom metrics."""

import time
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import structlog
from deepeval.metrics import AnswerRelevancyMetric, GEval, JsonCorrectnessMetric
from deepeval.test_case import LLMTestCase, SingleTurnParams
from pydantic import BaseModel

from tests.fixtures.golden_dataset import GoldenDataset

from .metrics.custom.risk_calibration import RiskCalibrationMetric
from .metrics.custom.sentiment_agreement import SentimentAgreementMetric
from .metrics.custom.topic_accuracy import TopicAccuracyMetric

logger = structlog.get_logger(__name__)


class DeepEvalMetric(Protocol):
    """Protocol for DeepEval metrics to satisfy Mypy."""

    score: float
    threshold: float
    reason: str | None

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> Any: ...

    def is_successful(self) -> bool: ...


class AISentenceOutput(BaseModel):
    """Schema for AI analysis output validation."""

    sent_id: str
    AI_Duygu_Skoru: float | None = None
    AI_Risk_Skoru: int | None = None
    AI_Potansiyel_Risk: str | None = None
    AI_Diplomatik_Ton: str | None = None
    AI_Manipulasyon_Skor: float | None = None
    AI_Talep_Var: int | None = None
    AI_Birincil_Konu: str | None = None
    AI_Cerceveleme: str | None = None


class EvaluationResult(BaseModel):
    """Single metric evaluation result."""

    metric_name: str
    score: float  # 0.0 - 1.0
    threshold: float
    passed: bool
    reason: str | None
    latency_ms: int


class QualityReport(BaseModel):
    """Complete quality evaluation report."""

    fixture_id: str
    overall_score: float
    passed: bool
    details: list[EvaluationResult]
    model_used: str
    backend_used: str
    evaluated_at: datetime


class QualityEvaluator:
    """Evaluates AI analysis quality using multiple metrics."""

    def __init__(self, model_name: str = "gpt-4", backend_used: str = "openai") -> None:
        self.model_name = model_name
        self.backend_used = backend_used
        self.logger = structlog.get_logger(__name__)
        self.golden_dataset = GoldenDataset()

        # Initialize custom metrics
        self.custom_metrics = {
            "sentiment_agreement": SentimentAgreementMetric(),
            "risk_calibration": RiskCalibrationMetric(),
            "topic_accuracy": TopicAccuracyMetric(),
        }

        # Initialize deepeval metrics
        self.deepeval_metrics: dict[str, DeepEvalMetric] = self._init_deepeval_metrics()

    def _init_deepeval_metrics(self) -> dict[str, DeepEvalMetric]:
        """Initialize Deepeval metrics."""
        # G-Eval for diplomatic analysis
        diplomatic_criteria = """
        Evaluate whether the AI correctly analyzes the diplomatic tone and intent of the
        given sentence.
        Consider:
        1. Identification of speaker's emotional state
        2. Recognition of diplomatic strategies
        3. Assessment of potential implications
        4. Contextual appropriateness of analysis
        """

        geval_metric = GEval(
            name="Diplomatic Analysis",
            criteria=diplomatic_criteria,
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
            ],
        )

        # Answer relevancy for focus
        relevancy_metric = AnswerRelevancyMetric(threshold=0.7, model=self.model_name)

        # JSON correctness for parseability
        json_metric = JsonCorrectnessMetric(expected_schema=cast(Any, AISentenceOutput))

        return {
            "diplomatic_analysis": cast(DeepEvalMetric, geval_metric),
            "answer_relevancy": cast(DeepEvalMetric, relevancy_metric),
            "json_validity": cast(DeepEvalMetric, json_metric),
        }

    def evaluate_single_fixture(
        self,
        ai_output: dict[str, Any],
        ground_truth: dict[str, Any],
        source_text: str,
        fixture_id: str,
    ) -> QualityReport:
        """
        Evaluate a single AI output against ground truth.

        Args:
            ai_output: AI analysis output
            ground_truth: Ground truth annotations
            source_text: Original sentence text
            fixture_id: Fixture identifier

        Returns:
            QualityReport with evaluation results
        """
        # start_time = time.time()
        evaluation_results = []

        # Run custom metrics
        for custom_metric_name, custom_metric in self.custom_metrics.items():
            try:
                metric_start = time.time()
                # Cast to Any or a Protocol if available to call measure
                result = cast(Any, custom_metric).measure(ai_output, ground_truth)
                metric_latency = int((time.time() - metric_start) * 1000)

                evaluation_results.append(
                    EvaluationResult(
                        metric_name=custom_metric_name,
                        score=result.score,
                        threshold=result.threshold,
                        passed=result.passed,
                        reason=result.reason,
                        latency_ms=metric_latency,
                    )
                )

            except Exception as e:
                self.logger.error(f"Error in custom metric {custom_metric_name}: {e}")
                evaluation_results.append(
                    EvaluationResult(
                        metric_name=custom_metric_name,
                        score=0.0,
                        threshold=0.8,
                        passed=False,
                        reason=f"Metric error: {str(e)}",
                        latency_ms=0,
                    )
                )

        # Run deepeval metrics
        for de_metric_name, de_metric_raw in self.deepeval_metrics.items():
            try:
                de_metric = de_metric_raw
                metric_start = time.time()

                # Create test case
                test_case = LLMTestCase(
                    input=source_text,
                    actual_output=str(ai_output),
                    expected_output=str(ground_truth),
                )

                # Measure metric
                de_metric.measure(test_case)
                metric_latency = int((time.time() - metric_start) * 1000)

                evaluation_results.append(
                    EvaluationResult(
                        metric_name=de_metric_name,
                        score=de_metric.score,
                        threshold=de_metric.threshold,
                        passed=de_metric.is_successful(),
                        reason=getattr(de_metric, "reason", None),
                        latency_ms=metric_latency,
                    )
                )

            except Exception as e:
                self.logger.error(f"Error in deepeval metric {de_metric_name}: {e}")
                evaluation_results.append(
                    EvaluationResult(
                        metric_name=de_metric_name,
                        score=0.0,
                        threshold=0.7,
                        passed=False,
                        reason=f"Deepeval error: {str(e)}",
                        latency_ms=0,
                    )
                )

        # Calculate overall score (weighted average)
        overall_score = self._calculate_overall_score(evaluation_results)
        passed = overall_score >= 0.8 and all(r.passed for r in evaluation_results)

        # total_latency = int((time.time() - start_time) * 1000)

        return QualityReport(
            fixture_id=fixture_id,
            overall_score=overall_score,
            passed=passed,
            details=evaluation_results,
            model_used=self.model_name,
            backend_used=self.backend_used,
            evaluated_at=datetime.now(UTC),
        )

    def _calculate_overall_score(self, results: list[EvaluationResult]) -> float:
        """Calculate weighted overall score."""
        # Custom metrics have higher weight
        weights = {
            "sentiment_agreement": 0.25,
            "risk_calibration": 0.20,
            "topic_accuracy": 0.15,
            "diplomatic_analysis": 0.20,
            "answer_relevancy": 0.10,
            "json_validity": 0.10,
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for result in results:
            weight = weights.get(result.metric_name, 0.05)
            weighted_sum += result.score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def evaluate_batch(
        self,
        ai_results: list[dict[str, Any]],
        source_texts: list[str],
        fixture_ids: list[str],
    ) -> list[QualityReport]:
        """
        Evaluate batch of AI results.

        Args:
            ai_results: List of AI analysis outputs
            source_texts: List of original sentence texts
            fixture_ids: List of fixture IDs

        Returns:
            List of QualityReport objects
        """
        if len(ai_results) != len(source_texts) or len(ai_results) != len(fixture_ids):
            raise ValueError("Input lists must have the same length")

        reports = []

        for _, (ai_output, source_text, fixture_id) in enumerate(
            zip(ai_results, source_texts, fixture_ids, strict=False)
        ):
            try:
                # Get ground truth from golden dataset
                fixture = self.golden_dataset.get_fixture_by_id(fixture_id)
                if not fixture:
                    self.logger.warning(
                        f"Fixture {fixture_id} not found in golden dataset"
                    )
                    continue

                ground_truth = fixture["ground_truth"]

                # Evaluate
                report = self.evaluate_single_fixture(
                    ai_output, ground_truth, source_text, fixture_id
                )
                reports.append(report)

                self.logger.info(
                    f"Evaluated fixture {fixture_id}: score={report.overall_score:.3f}"
                )

            except Exception as e:
                self.logger.error(f"Error evaluating fixture {fixture_id}: {e}")
                continue

        return reports

    def evaluate_golden_dataset(
        self, ai_results: list[dict[str, Any]], limit: int | None = None
    ) -> dict[str, Any]:
        """
        Evaluate against entire golden dataset.

        Args:
            ai_results: AI results matching golden dataset order
            limit: Optional limit on number of fixtures to evaluate

        Returns:
            Summary statistics and reports
        """
        dataset = self.golden_dataset.load_dataset()
        fixtures = dataset.get("fixtures", [])

        if limit:
            fixtures = fixtures[:limit]

        if len(ai_results) != len(fixtures):
            raise ValueError(
                f"AI results count ({len(ai_results)}) must match fixtures count "
                f"({len(fixtures)})"
            )

        reports = []

        for i, (fixture, ai_output) in enumerate(
            zip(fixtures, ai_results, strict=False)
        ):
            try:
                source_text = fixture["source_text"]
                fixture_id = fixture["fixture_id"]
                ground_truth = fixture["ground_truth"]

                report = self.evaluate_single_fixture(
                    ai_output, ground_truth, source_text, fixture_id
                )
                reports.append(report)

            except Exception as e:
                self.logger.error(
                    f"Error evaluating fixture {fixture.get('fixture_id', i)}: {e}"
                )
                continue

        # Calculate summary statistics
        summary = self._calculate_summary_statistics(reports)

        return {
            "summary": summary,
            "reports": reports,
            "total_fixtures": len(fixtures),
            "evaluated_fixtures": len(reports),
            "model_used": self.model_name,
            "backend_used": self.backend_used,
            "evaluated_at": datetime.utcnow().isoformat(),
        }

    def _calculate_summary_statistics(
        self, reports: list[QualityReport]
    ) -> dict[str, Any]:
        """Calculate summary statistics from evaluation reports."""
        if not reports:
            return {}

        overall_scores = [r.overall_score for r in reports]
        passed_count = sum(1 for r in reports if r.passed)

        # Metric-specific statistics
        metric_stats = {}
        all_metrics: set[str] = set()
        for report in reports:
            all_metrics.update(detail.metric_name for detail in report.details)

        for metric in all_metrics:
            scores = [
                detail.score
                for report in reports
                for detail in report.details
                if detail.metric_name == metric
            ]
            if scores:
                metric_stats[metric] = {
                    "mean_score": sum(scores) / len(scores),
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "pass_rate": sum(1 for s in scores if s >= 0.8) / len(scores),
                }

        return {
            "overall_mean_score": sum(overall_scores) / len(overall_scores),
            "overall_min_score": min(overall_scores),
            "overall_max_score": max(overall_scores),
            "overall_pass_rate": passed_count / len(reports),
            "total_reports": len(reports),
            "metric_statistics": metric_stats,
        }
