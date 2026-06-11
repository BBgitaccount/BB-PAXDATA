"""Conditional detection service for demand analysis."""

import re
from typing import Protocol


class ConditionalDetectorProtocol(Protocol):
    """Protocol for conditional detection."""

    def is_conditional(self, text: str) -> bool:
        """Check if text contains conditional markers.

        Args:
            text: Text to analyze

        Returns:
            True if text is conditional, False otherwise
        """
        ...

    def extract_conditions(self, text: str) -> list[str]:
        """Extract conditions from conditional text.

        Args:
            text: Text to analyze

        Returns:
            List of condition strings
        """
        ...


class ConditionalDetector:
    """Detect conditional demands and extract conditions."""

    def is_conditional(self, text: str) -> bool:
        """Check if text contains conditional markers.

        Args:
            text: Text to analyze

        Returns:
            True if text is conditional, False otherwise
        """
        conditional_markers = [
            "if",
            "provided that",
            "on condition that",
            "subject to",
            "assuming",
            "unless",
            "in case",
            "contingent on",
        ]

        text_lower = text.lower()
        return any(marker in text_lower for marker in conditional_markers)

    def extract_conditions(self, text: str) -> list[str]:
        """Extract conditions from conditional text.

        Args:
            text: Text to analyze

        Returns:
            List of condition strings
        """
        conditions = []

        # Simple pattern matching for conditions
        patterns = [
            r"if\s+(.+?)[,;.]",
            r"provided\s+that\s+(.+?)[,;.]",
            r"subject\s+to\s+(.+?)[,;.]",
            r"assuming\s+(.+?)[,;.]",
            r"unless\s+(.+?)[,;.]",
            r"in\s+case\s+(.+?)[,;.]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                condition = match.strip()
                if condition and len(condition) > 3:  # Filter out short matches
                    conditions.append(condition)

        return conditions
