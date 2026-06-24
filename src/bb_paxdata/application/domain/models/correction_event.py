"""
Correction Event Domain Model

Represents a human correction to AI-generated analysis.
Append-only: once created, corrections cannot be modified or deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class CorrectionEvent:
    """
    Immutable correction event for learning from human feedback.

    Each correction captures:
    - What was corrected: sentence_id, field_corrected
    - The change: original_value -> corrected_value
    - Context: prompt_version, ai_confidence, context_snapshot
    - Who/when: corrector_id, timestamp

    This model is append-only - corrections cannot be modified or deleted.
    """

    id: str
    sentence_id: str
    field_corrected: str  # e.g., "sentiment", "frame", "discourse_act", "risk_score"
    original_value: Any
    corrected_value: Any
    prompt_version: str
    ai_confidence: float  # 0.0 to 1.0
    corrector_id: str  # ID of the human who made the correction
    timestamp: datetime
    context_snapshot: dict[str, Any] | None = (
        None  # Pipeline state at time of correction
    )

    def compute_delta(self) -> Any:
        """
        Compute the delta between corrected and original values.

        For numeric values, returns the difference.
        For categorical values, returns a tuple (original, corrected).
        """
        if isinstance(self.original_value, int | float) and isinstance(
            self.corrected_value, int | float
        ):
            return self.corrected_value - self.original_value
        return (self.original_value, self.corrected_value)

    def is_high_confidence_error(self) -> bool:
        """
        Determine if this correction represents a high-confidence AI error.

        Returns True if AI confidence was high (>0.7) but still required correction.
        """
        return self.ai_confidence > 0.7


@dataclass
class CorrectionStats:
    """Statistics for correction events."""

    total_corrections: int
    by_field: dict[str, int]
    by_prompt_version: dict[str, int]
    high_confidence_errors: int
    average_confidence: float
    correction_rate: float  # corrections / total analyzed
