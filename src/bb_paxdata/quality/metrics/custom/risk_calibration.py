"""Risk calibration metric for evaluating AI risk scoring against ground truth."""

from typing import Any

import numpy as np
import structlog
from pydantic import BaseModel
from scipy.stats import spearmanr

logger = structlog.get_logger(__name__)


class MetricResult(BaseModel):
    """Result of a single metric evaluation."""

    score: float  # 0.0 - 1.0
    threshold: float
    passed: bool
    reason: str | None


class RiskCalibrationMetric:
    """Measures calibration of AI risk scores against ground truth."""

    def __init__(self, threshold: float = 0.7, min_samples: int = 3):
        self.threshold = threshold
        self.min_samples = min_samples
        self.logger = structlog.get_logger(__name__)

    def measure(
        self, ai_output: dict[str, Any], ground_truth: dict[str, Any]
    ) -> MetricResult:
        """
        Measure risk calibration for a single sentence.

        For single sentence, we check if risk level categorization matches.

        Args:
            ai_output: AI analysis output containing risk scores
            ground_truth: Ground truth annotations

        Returns:
            MetricResult with calibration score
        """
        try:
            ai_risk = ai_output.get("AI_Risk_Skoru")
            ai_potential = ai_output.get("AI_Potansiyel_Risk")
            gt_risk = ground_truth.get("AI_Risk_Skoru")
            gt_potential = ground_truth.get("AI_Potansiyel_Risk")

            if ai_risk is None or gt_risk is None:
                return MetricResult(
                    score=0.0,
                    threshold=self.threshold,
                    passed=False,
                    reason="Missing risk scores in AI output or ground truth",
                )

            # Primary check: numerical score agreement within tolerance
            score_diff = abs(ai_risk - gt_risk)
            max_diff = 2.0  # Acceptable difference in risk scores

            if score_diff <= max_diff:
                # Linear scoring based on difference
                score = 1.0 - (score_diff / max_diff) * 0.3
            else:
                # Exponential decay for large differences
                score = 0.7 * (0.8 ** ((score_diff - max_diff) / max_diff))

            # Secondary check: categorical agreement
            if ai_potential and gt_potential:
                if ai_potential == gt_potential:
                    score = min(1.0, score + 0.1)  # Bonus for exact category match
                elif self._risk_level_distance(ai_potential, gt_potential) <= 1:
                    score = min(
                        1.0, score + 0.05
                    )  # Small bonus for adjacent categories

            score = max(0.0, min(1.0, score))
            passed = score >= self.threshold

            reason = (
                f"Risk score difference: {score_diff:.1f} "
                f"(AI: {ai_risk}, GT: {gt_risk})"
            )

            return MetricResult(
                score=score, threshold=self.threshold, passed=passed, reason=reason
            )

        except Exception as e:
            self.logger.error(f"Error measuring risk calibration: {e}")
            return MetricResult(
                score=0.0,
                threshold=self.threshold,
                passed=False,
                reason=f"Measurement error: {str(e)}",
            )

    def measure_batch(
        self, ai_outputs: list[dict[str, Any]], ground_truths: list[dict[str, Any]]
    ) -> MetricResult:
        """
        Measure risk calibration for a batch using Spearman rank correlation.

        Args:
            ai_outputs: List of AI analysis outputs
            ground_truths: List of ground truth annotations

        Returns:
            MetricResult with batch calibration score
        """
        if len(ai_outputs) != len(ground_truths):
            raise ValueError("AI outputs and ground truths must have same length")

        if len(ai_outputs) < self.min_samples:
            return MetricResult(
                score=0.0,
                threshold=self.threshold,
                passed=False,
                reason=(
                    f"Insufficient samples for batch evaluation (need >= "
                    f"{self.min_samples})"
                ),
            )

        try:
            # Extract risk scores
            ai_risks = []
            gt_risks = []

            for ai_output, ground_truth in zip(ai_outputs, ground_truths, strict=False):
                ai_risk = ai_output.get("AI_Risk_Skoru")
                gt_risk = ground_truth.get("AI_Risk_Skoru")

                if ai_risk is not None and gt_risk is not None:
                    ai_risks.append(ai_risk)
                    gt_risks.append(gt_risk)

            if len(ai_risks) < self.min_samples:
                return MetricResult(
                    score=0.0,
                    threshold=self.threshold,
                    passed=False,
                    reason=(
                        f"Insufficient valid risk scores for batch evaluation "
                        f"(need >= {self.min_samples})"
                    ),
                )

            # Calculate Spearman rank correlation
            correlation, p_value = spearmanr(ai_risks, gt_risks)

            if np.isnan(correlation):
                score = 0.0
                reason = "Unable to calculate rank correlation (constant values)"
            else:
                # Convert correlation (-1 to 1) to score (0 to 1)
                score = (correlation + 1.0) / 2.0
                reason = (
                    f"Spearman correlation: {correlation:.3f} (p-value: {p_value:.3f})"
                )

            passed = score >= self.threshold

            self.logger.debug(
                "Risk calibration batch measurement",
                sample_count=len(ai_risks),
                correlation=correlation,
                score=score,
                passed=passed,
            )

            return MetricResult(
                score=score, threshold=self.threshold, passed=passed, reason=reason
            )

        except Exception as e:
            self.logger.error(f"Error in batch risk calibration: {e}")
            return MetricResult(
                score=0.0,
                threshold=self.threshold,
                passed=False,
                reason=f"Batch measurement error: {str(e)}",
            )

    def _risk_level_distance(self, level1: str, level2: str) -> int:
        """Calculate distance between risk levels."""
        levels = ["none", "low", "medium", "high", "critical"]

        try:
            idx1 = levels.index(level1)
            idx2 = levels.index(level2)
            return abs(idx1 - idx2)
        except ValueError:
            return 2  # Maximum distance for unknown levels
