"""Sentiment agreement metric for evaluating AI sentiment analysis."""

from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class MetricResult(BaseModel):
    """Result of a single metric evaluation."""

    score: float  # 0.0 - 1.0
    threshold: float
    passed: bool
    reason: str | None


class SentimentAgreementMetric:
    """Measures agreement between AI sentiment score and ground truth."""

    def __init__(self, threshold: float = 0.8, tolerance: float = 0.3):
        self.threshold = threshold
        self.tolerance = tolerance  # Acceptable difference in sentiment scores
        self.logger = structlog.get_logger(__name__)

    def measure(
        self, ai_output: dict[str, Any], ground_truth: dict[str, Any]
    ) -> MetricResult:
        """
        Measure sentiment agreement between AI output and ground truth.

        Args:
            ai_output: AI analysis output containing AI_Duygu_Skoru
            ground_truth: Ground truth annotations containing AI_Duygu_Skoru

        Returns:
            MetricResult with agreement score and pass/fail status
        """
        try:
            ai_sentiment = ai_output.get("AI_Duygu_Skoru")
            gt_sentiment = ground_truth.get("AI_Duygu_Skoru")

            if ai_sentiment is None or gt_sentiment is None:
                return MetricResult(
                    score=0.0,
                    threshold=self.threshold,
                    passed=False,
                    reason="Missing sentiment scores in AI output or ground truth",
                )

            # Calculate absolute difference
            diff = abs(ai_sentiment - gt_sentiment)

            # Convert difference to agreement score (0.0 to 1.0)
            # Perfect agreement (diff=0) -> score=1.0
            # Max acceptable difference (diff=tolerance) -> score=threshold
            # Beyond tolerance -> score < threshold

            if diff <= self.tolerance:
                # Linear interpolation within tolerance
                score = 1.0 - (diff / self.tolerance) * (1.0 - self.threshold)
            else:
                # Exponential decay beyond tolerance
                score = self.threshold * (
                    0.5 ** ((diff - self.tolerance) / self.tolerance)
                )

            # Ensure score is within bounds
            score = max(0.0, min(1.0, score))

            passed = score >= self.threshold

            # Generate reason
            if passed:
                reason = f"Sentiment scores agree within tolerance (diff={diff:.3f})"
            else:
                reason = (
                    f"Sentiment scores differ beyond tolerance (diff={diff:.3f}, "
                    f"tolerance={self.tolerance})"
                )

            self.logger.debug(
                "Sentiment agreement measured",
                ai_sentiment=ai_sentiment,
                gt_sentiment=gt_sentiment,
                diff=diff,
                score=score,
                passed=passed,
            )

            return MetricResult(
                score=score, threshold=self.threshold, passed=passed, reason=reason
            )

        except Exception as e:
            self.logger.error(f"Error measuring sentiment agreement: {e}")
            return MetricResult(
                score=0.0,
                threshold=self.threshold,
                passed=False,
                reason=f"Measurement error: {e!s}",
            )

    def measure_batch(
        self, ai_outputs: list[dict[str, Any]], ground_truths: list[dict[str, Any]]
    ) -> list[MetricResult]:
        """
        Measure sentiment agreement for a batch of outputs.

        Args:
            ai_outputs: List of AI analysis outputs
            ground_truths: List of ground truth annotations

        Returns:
            List of MetricResult objects
        """
        if len(ai_outputs) != len(ground_truths):
            raise ValueError("AI outputs and ground truths must have same length")

        results = []
        for ai_output, ground_truth in zip(ai_outputs, ground_truths, strict=False):
            result = self.measure(ai_output, ground_truth)
            results.append(result)

        return results
