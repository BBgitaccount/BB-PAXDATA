"""
Weight Calibration Domain Models

Defines calibratable parameters for the analysis pipeline and weight update proposals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ParameterType(StrEnum):
    """Types of calibratable parameters."""

    SENTIMENT_WEIGHT = "sentiment_weight"
    RISK_THRESHOLD = "risk_threshold"
    HEDGING_WEIGHT = "hedging_weight"
    WORDFISH_SMOOTHING = "wordfish_smoothing"


class ProposalStatus(StrEnum):
    """Status of weight update proposals."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVATED = "activated"
    ROLLED_BACK = "rolled_back"


@dataclass
class CalibratableParameter:
    """
    A calibratable parameter in the analysis pipeline.

    Examples:
    - SentimentFormula weights (e.g., sentiment_weight_pos, sentiment_weight_neg)
    - RiskScorer thresholds (e.g., risk_threshold_high, risk_threshold_medium)
    - HedgingQuantifier weights (e.g., hedging_weight_moderate, hedging_weight_strong)
    - Wordfish smoothing parameters (e.g., wordfish_smoothing_alpha)
    """

    id: str
    name: str
    parameter_type: ParameterType
    current_value: float
    min_value: float
    max_value: float
    description: str
    last_updated: datetime
    version: int = 1

    def is_valid_value(self, value: float) -> bool:
        """Check if a value is within valid bounds."""
        return self.min_value <= value <= self.max_value


@dataclass
class WeightUpdateProposal:
    """
    A proposal to update calibratable parameters based on correction signals.

    Created automatically by the WeightCalibrator based on correction patterns.
    Requires human approval (HITL) before activation.
    """

    id: str
    parameter_id: str
    parameter_name: str
    old_value: float
    proposed_value: float
    correction_signal: float  # The computed signal from corrections
    learning_rate: float  # Learning rate used for this update
    confidence: float  # Confidence in this proposal (0.0 to 1.0)
    reason: str  # Human-readable explanation
    created_at: datetime
    status: ProposalStatus = ProposalStatus.PENDING
    approved_by: str | None = None  # ID of human approver
    approved_at: datetime | None = None
    activated_at: datetime | None = None
    rollback_version: int | None = None  # Version to rollback to if needed
    metadata: dict[str, Any] = field(default_factory=dict)

    def apply(self) -> CalibratableParameter:
        """
        Apply this proposal to create an updated parameter.

        Returns a new CalibratableParameter with the proposed value.
        """
        return CalibratableParameter(
            id=self.parameter_id,
            name=self.parameter_name,
            parameter_type=ParameterType.SENTIMENT_WEIGHT,  # Will be set by caller
            current_value=self.proposed_value,
            min_value=0.0,  # Will be set by caller
            max_value=1.0,  # Will be set by caller
            description="Updated via weight calibration",
            last_updated=datetime.utcnow(),
            version=self.rollback_version + 1 if self.rollback_version else 1,
        )


@dataclass
class WeightVersionHistory:
    """
    Historical record of weight versions for rollback support.

    Tracks all previous versions of calibratable parameters.
    """

    id: str
    parameter_id: str
    version: int
    value: float
    created_at: datetime
    created_by: str  # "system" or user ID
    reason: str
    proposal_id: str | None = (
        None  # Reference to the proposal that created this version
    )


@dataclass
class CorrectionSignal:
    """
    Computed correction signal for a parameter.

    Represents the aggregate correction signal from multiple correction events.
    """

    parameter_id: str
    signal: float  # Normalized to [-1, 1]
    sample_size: int  # Number of corrections used to compute signal
    variance: float  # Variance of corrections (for stability check)
    computed_at: datetime
    field_name: str | None = None  # Field this signal is based on (e.g., "sentiment")
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_stable(self, variance_threshold: float = 0.5) -> bool:
        """Check if the signal is stable (low variance)."""
        return self.variance < variance_threshold

    def has_sufficient_samples(self, min_samples: int = 100) -> bool:
        """Check if we have enough correction samples."""
        return self.sample_size >= min_samples
