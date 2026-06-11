"""Assertiveness detection service for demand analysis."""

from typing import Protocol


class AssertivenessDetectorProtocol(Protocol):
    """Protocol for assertiveness detection."""

    def detect_assertiveness(self, text: str) -> float:
        """Detect assertiveness level of text.

        Args:
            text: Text to analyze

        Returns:
            Assertiveness score between 0.0 and 1.0
        """
        ...


class AssertivenessDetector:
    """Detect assertiveness level in demand text."""

    def detect_assertiveness(self, text: str) -> float:
        """Detect assertiveness level of text.

        Args:
            text: Text to analyze

        Returns:
            Assertiveness score between 0.0 and 1.0
        """
        text_lower = text.lower()

        # High assertiveness markers
        high_markers = [
            "must",
            "require",
            "demand",
            "insist",
            "imperative",
            "expect",
            "need",
        ]
        # Medium assertiveness markers
        med_markers = [
            "should",
            "ought",
            "need to",
            "expect to",
            "have to",
        ]
        # Low assertiveness markers
        low_markers = [
            "suggest",
            "propose",
            "consider",
            "would like",
            "could",
            "might",
        ]

        score = 0.5  # Default

        if any(marker in text_lower for marker in high_markers):
            score = 0.9
        elif any(marker in text_lower for marker in med_markers):
            score = 0.7
        elif any(marker in text_lower for marker in low_markers):
            score = 0.3

        return score
