"""Topic accuracy metric for evaluating AI topic classification against ground truth."""

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


class TopicAccuracyMetric:
    """Measures accuracy of AI topic classification against ground truth."""

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
        self.logger = structlog.get_logger(__name__)

        # Topic mapping for partial matches
        self.topic_groups = {
            "Güvenlik_Çatışma": [
                "security",
                "conflict",
                "defense",
                "military",
                "threat",
            ],
            "Ekonomi": [
                "economy",
                "economic",
                "trade",
                "finance",
                "market",
                "currency",
            ],
            "Diplomasi": ["diplomacy", "diplomatic", "negotiation", "talks", "summit"],
            "İnsani_Yardım": ["humanitarian", "aid", "refugee", "relief", "assistance"],
            "BM_Reformu": ["un", "reform", "united nations", "security council"],
            "Gazze": ["gaza", "gazze", "palestine", "israel", "hamas"],
            "Ukrayna": ["ukraine", "russia", "kyiv", "moscow", "war"],
            "Çok_kutupluluk": ["multipolar", "brics", "china", "russia", "west"],
        }

    def measure(
        self, ai_output: dict[str, Any], ground_truth: dict[str, Any]
    ) -> MetricResult:
        """
        Measure topic accuracy between AI output and ground truth.

        Args:
            ai_output: AI analysis output containing AI_Birincil_Konu
            ground_truth: Ground truth annotations containing AI_Birincil_Konu

        Returns:
            MetricResult with accuracy score and pass/fail status
        """
        try:
            ai_topic = ai_output.get("AI_Birincil_Konu")
            gt_topic = ground_truth.get("AI_Birincil_Konu")

            if ai_topic is None or gt_topic is None:
                return MetricResult(
                    score=0.0,
                    threshold=self.threshold,
                    passed=False,
                    reason="Missing topic classification in AI output or ground truth",
                )

            # Normalize topics (lowercase, remove underscores, spaces)
            ai_normalized = self._normalize_topic(ai_topic)
            gt_normalized = self._normalize_topic(gt_topic)

            # Exact match
            if ai_normalized == gt_normalized:
                score = 1.0
                reason = f"Exact topic match: '{ai_topic}'"
            else:
                # Check for partial match within topic groups
                score = self._calculate_partial_match_score(ai_topic, gt_topic)
                if score >= 0.7:
                    reason = f"Partial topic match: '{ai_topic}' vs '{gt_topic}'"
                else:
                    reason = f"Topic mismatch: '{ai_topic}' vs '{gt_topic}'"

            passed = score >= self.threshold

            self.logger.debug(
                "Topic accuracy measured",
                ai_topic=ai_topic,
                gt_topic=gt_topic,
                score=score,
                passed=passed,
            )

            return MetricResult(
                score=score, threshold=self.threshold, passed=passed, reason=reason
            )

        except Exception as e:
            self.logger.error(f"Error measuring topic accuracy: {e}")
            return MetricResult(
                score=0.0,
                threshold=self.threshold,
                passed=False,
                reason=f"Measurement error: {e!s}",
            )

    def _normalize_topic(self, topic: str) -> str:
        """Normalize topic string for comparison."""
        if not topic:
            return ""

        # Convert to lowercase and replace underscores/special chars with spaces
        normalized = topic.lower().replace("_", " ").replace("-", " ")

        # Remove extra spaces
        normalized = " ".join(normalized.split())

        return normalized

    def _calculate_partial_match_score(self, ai_topic: str, gt_topic: str) -> float:
        """Calculate partial match score based on topic groups."""
        ai_normalized = self._normalize_topic(ai_topic)
        gt_normalized = self._normalize_topic(gt_topic)

        # Check if both topics belong to same group
        for _, keywords in self.topic_groups.items():
            ai_in_group = any(keyword in ai_normalized for keyword in keywords)
            gt_in_group = any(keyword in gt_normalized for keyword in keywords)

            if ai_in_group and gt_in_group:
                # Same group, but not exact match
                return 0.8

        # Check for keyword overlap
        ai_words = set(ai_normalized.split())
        gt_words = set(gt_normalized.split())

        if ai_words and gt_words:
            # Jaccard similarity
            intersection = ai_words.intersection(gt_words)
            union = ai_words.union(gt_words)
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard > 0.3:
                return min(0.6, jaccard + 0.2)

        # Check substring matches
        if ai_normalized in gt_normalized or gt_normalized in ai_normalized:
            return 0.5

        # No significant match
        return 0.2

    def measure_batch(
        self, ai_outputs: list[dict[str, Any]], ground_truths: list[dict[str, Any]]
    ) -> list[MetricResult]:
        """
        Measure topic accuracy for a batch of outputs.

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

    def get_topic_statistics(self, results: list[MetricResult]) -> dict[str, Any]:
        """
        Calculate topic-specific statistics from batch results.

        Args:
            results: List of MetricResult objects

        Returns:
            Dictionary with topic statistics
        """
        if not results:
            return {}

        total_count = len(results)
        passed_count = sum(1 for r in results if r.passed)
        scores = [r.score for r in results]

        return {
            "total_evaluations": total_count,
            "passed_evaluations": passed_count,
            "pass_rate": passed_count / total_count if total_count > 0 else 0.0,
            "average_score": sum(scores) / len(scores) if scores else 0.0,
            "min_score": min(scores) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0,
        }
