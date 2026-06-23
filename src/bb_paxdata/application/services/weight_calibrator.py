"""
Weight Calibrator Service

Implements gradient-like weight updates based on correction signals.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.weight_calibration import (
    CalibratableParameter,
    CorrectionSignal,
    ParameterType,
    ProposalStatus,
    WeightUpdateProposal,
)
from bb_paxdata.infrastructure.db.repositories.correction_event_repository import (
    CorrectionEventRepository,
)

logger = structlog.get_logger(__name__)


class WeightCalibrator:
    """
    Calibrates analysis weights based on correction signals.

    Implements gradient-like updates:
    - new_weight = old_weight + lr * correction_signal
    - correction_signal = mean(corrected - original)
    - Normalized to [-1, 1]
    """

    def __init__(
        self,
        db: AsyncSession,
        correction_repo: CorrectionEventRepository,
        default_learning_rate: float = 0.1,
    ) -> None:
        self._db = db
        self._correction_repo = correction_repo
        self._default_learning_rate = default_learning_rate

    async def compute_correction_signal(
        self,
        field: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> CorrectionSignal:
        """
        Compute correction signal for a specific field.

        Args:
            field: Field to analyze (e.g., "sentiment", "risk_score")
            start_date: Optional start date for correction events
            end_date: Optional end date for correction events

        Returns:
            CorrectionSignal with computed signal and statistics
        """
        # Get field distribution
        distribution = await self._correction_repo.get_field_distribution(
            field=field, start_date=start_date, end_date=end_date
        )

        deltas = distribution.get("deltas", [])
        sample_size = len(deltas)

        if sample_size == 0:
            return CorrectionSignal(
                parameter_id=f"signal_{field}",
                signal=0.0,
                sample_size=0,
                variance=0.0,
                computed_at=datetime.utcnow(),
                field_name=field,
            )

        # Compute mean delta (correction signal)
        numeric_deltas = []
        for delta in deltas:
            if isinstance(delta, (int, float)):
                numeric_deltas.append(delta)
            elif isinstance(delta, tuple) and len(delta) == 2:
                # For categorical corrections, use -1 or +1 based on direction
                numeric_deltas.append(1.0)  # Simplified: always positive signal

        if not numeric_deltas:
            return CorrectionSignal(
                parameter_id=f"signal_{field}",
                signal=0.0,
                sample_size=0,
                variance=0.0,
                computed_at=datetime.utcnow(),
                field_name=field,
            )

        mean_delta = sum(numeric_deltas) / len(numeric_deltas)

        # Normalize to [-1, 1]
        # For sentiment: -1 (too negative) to +1 (too positive)
        # For risk_score: -1 (too low) to +1 (too high)
        normalized_signal = self._normalize_signal(mean_delta, field)

        # Compute variance
        variance = sum((d - mean_delta) ** 2 for d in numeric_deltas) / len(
            numeric_deltas
        )

        return CorrectionSignal(
            parameter_id=f"signal_{field}",
            signal=normalized_signal,
            sample_size=len(numeric_deltas),
            variance=variance,
            computed_at=datetime.utcnow(),
            field_name=field,
        )

    def _normalize_signal(self, signal: float, field: str) -> float:
        """
        Normalize signal to [-1, 1] range.

        Different fields have different scales, so we normalize accordingly.
        """
        # Field-specific normalization
        if field == "sentiment":
            # Sentiment is typically in [-1, 1], so minimal normalization needed
            return max(-1.0, min(1.0, signal))
        elif field == "risk_score":
            # Risk score is typically in [0, 1], normalize to [-1, 1]
            return max(-1.0, min(1.0, (signal - 0.5) * 2))
        elif field == "hedging":
            # Hedging is typically in [0, 1], normalize to [-1, 1]
            return max(-1.0, min(1.0, (signal - 0.5) * 2))
        else:
            # Default normalization: assume signal is already in reasonable range
            return max(-1.0, min(1.0, signal))

    async def propose_weight_update(
        self,
        parameter: CalibratableParameter,
        correction_signal: CorrectionSignal,
        learning_rate: float | None = None,
    ) -> WeightUpdateProposal:
        """
        Propose a weight update based on correction signal.

        Args:
            parameter: The parameter to update
            correction_signal: Computed correction signal
            learning_rate: Learning rate (defaults to default_learning_rate)

        Returns:
            WeightUpdateProposal with proposed new value
        """
        lr = learning_rate or self._default_learning_rate

        # Compute proposed value: new = old + lr * signal
        delta = lr * correction_signal.signal
        proposed_value = parameter.current_value + delta

        # Clamp to valid range
        proposed_value = max(
            parameter.min_value, min(parameter.max_value, proposed_value)
        )

        # Compute confidence based on sample size and stability
        confidence = self._compute_proposal_confidence(correction_signal)

        # Generate human-readable reason
        reason = self._generate_proposal_reason(
            parameter, correction_signal, delta, confidence
        )

        proposal = WeightUpdateProposal(
            id=str(uuid.uuid4()),
            parameter_id=parameter.id,
            parameter_name=parameter.name,
            old_value=parameter.current_value,
            proposed_value=proposed_value,
            correction_signal=correction_signal.signal,
            learning_rate=lr,
            confidence=confidence,
            reason=reason,
            created_at=datetime.utcnow(),
            status=ProposalStatus.PENDING,
            rollback_version=parameter.version,
        )

        logger.info(
            "weight_update_proposed",
            parameter=parameter.name,
            old_value=parameter.current_value,
            proposed_value=proposed_value,
            signal=correction_signal.signal,
            confidence=confidence,
        )

        return proposal

    def _compute_proposal_confidence(self, signal: CorrectionSignal) -> float:
        """
        Compute confidence in the proposal based on signal statistics.

        Higher confidence when:
        - Large sample size
        - Low variance (stable signal)
        - Strong signal magnitude
        """
        # Sample size factor (0 to 1, saturating at 1000 samples)
        sample_factor = min(1.0, signal.sample_size / 1000.0)

        # Stability factor (inverse of variance, 0 to 1)
        stability_factor = max(0.0, 1.0 - signal.variance / 2.0)

        # Signal magnitude factor (0 to 1)
        magnitude_factor = min(1.0, abs(signal.signal))

        # Combined confidence
        confidence = (
            (sample_factor * 0.4) + (stability_factor * 0.3) + (magnitude_factor * 0.3)
        )

        return confidence

    def _generate_proposal_reason(
        self,
        parameter: CalibratableParameter,
        signal: CorrectionSignal,
        delta: float,
        confidence: float,
    ) -> str:
        """Generate human-readable reason for the proposal."""
        direction = "increase" if delta > 0 else "decrease"
        magnitude = abs(delta)

        reason_parts = [
            f"Based on {signal.sample_size} corrections for {signal.field_name or 'this parameter'}, ",
            f"correction signal is {signal.signal:.3f}. ",
            f"Proposing to {direction} {parameter.name} by {magnitude:.3f} ",
            f"(from {parameter.current_value:.3f} to {parameter.current_value + delta:.3f}). ",
            f"Confidence: {confidence:.2f} based on sample size and stability.",
        ]

        if not signal.is_stable():
            reason_parts.append(" Warning: Signal variance is high.")

        return "".join(reason_parts)

    async def batch_propose_updates(
        self,
        parameters: Sequence[CalibratableParameter],
        field_signals: dict[str, CorrectionSignal],
        learning_rate: float | None = None,
    ) -> list[WeightUpdateProposal]:
        """
        Batch propose updates for multiple parameters.

        Args:
            parameters: List of parameters to update
            field_signals: Mapping of field names to correction signals
            learning_rate: Learning rate (defaults to default_learning_rate)

        Returns:
            List of WeightUpdateProposal objects
        """
        proposals = []

        for param in parameters:
            # Find matching signal based on parameter type/name
            signal = self._find_matching_signal(param, field_signals)

            if signal and signal.has_sufficient_samples():
                proposal = await self.propose_weight_update(
                    parameter=param,
                    correction_signal=signal,
                    learning_rate=learning_rate,
                )
                proposals.append(proposal)

        logger.info(
            "batch_weight_updates_proposed",
            total_parameters=len(parameters),
            proposals_created=len(proposals),
        )

        return proposals

    def _find_matching_signal(
        self,
        parameter: CalibratableParameter,
        field_signals: dict[str, CorrectionSignal],
    ) -> CorrectionSignal | None:
        """Find the correction signal that matches a parameter."""
        param_name_lower = parameter.name.lower()

        # Try to match by field name in parameter name
        for field, signal in field_signals.items():
            if field.lower() in param_name_lower:
                return signal

        # Try to match by parameter type
        if parameter.parameter_type == ParameterType.SENTIMENT_WEIGHT:
            return field_signals.get("sentiment")
        elif parameter.parameter_type == ParameterType.RISK_THRESHOLD:
            return field_signals.get("risk_score")
        elif parameter.parameter_type == ParameterType.HEDGING_WEIGHT:
            return field_signals.get("hedging")

        return None
