"""
Calibration Security Service.

Implements safety mechanisms for weight and prompt calibration:
- Catastrophic forgetting protection
- Version pinning
- Rollback mechanisms
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.correction_event import CorrectionEvent
from bb_paxdata.application.domain.models.weight_calibration import (
    CalibratableParameter,
    CorrectionSignal,
    WeightUpdateProposal,
)

logger = structlog.get_logger(__name__)


class CalibrationSecurityService:
    """
    Security service for calibration operations.

    Prevents catastrophic forgetting and ensures version integrity.
    """

    def __init__(
        self,
        db: AsyncSession,
        min_correction_samples: int = 100,
        variance_threshold: float = 0.5,
    ) -> None:
        self._db = db
        self._min_correction_samples = min_correction_samples
        self._variance_threshold = variance_threshold

    def check_catastrophic_forgetting_risk(
        self,
        signal: CorrectionSignal,
    ) -> tuple[bool, str]:
        """
        Check if a calibration update poses catastrophic forgetting risk.

        Protection criteria:
        - Minimum N=100 correction samples required
        - Stability measurement (variance threshold)

        Args:
            signal: Correction signal to evaluate

        Returns:
            Tuple of (is_safe, reason)
        """
        # Check sample size
        if not signal.has_sufficient_samples(self._min_correction_samples):
            return (
                False,
                f"Insufficient correction samples: {signal.sample_size} < {self._min_correction_samples}",
            )

        # Check stability
        if not signal.is_stable(self._variance_threshold):
            return (
                False,
                f"Signal variance too high: {signal.variance:.3f} > {self._variance_threshold}",
            )

        return True, "Signal meets safety criteria"

    def validate_proposal_safety(
        self,
        proposal: WeightUpdateProposal,
        signal: CorrectionSignal,
    ) -> tuple[bool, str]:
        """
        Validate that a weight update proposal is safe to apply.

        Combines catastrophic forgetting checks with additional safety rules.
        """
        # Check catastrophic forgetting risk
        is_safe, reason = self.check_catastrophic_forgetting_risk(signal)
        if not is_safe:
            return False, reason

        # Check if the change is too drastic
        change_magnitude = abs(proposal.proposed_value - proposal.old_value)
        max_change = 0.5  # Maximum 50% change in one update

        if change_magnitude > max_change:
            return (
                False,
                f"Change magnitude too large: {change_magnitude:.3f} > {max_change}",
            )

        # Check confidence threshold
        if proposal.confidence < 0.5:
            return (
                False,
                f"Proposal confidence too low: {proposal.confidence:.2f} < 0.5",
            )

        return True, "Proposal is safe to apply"

    def check_version_pinning_compatibility(
        self,
        correction: CorrectionEvent,
        current_prompt_version: str,
    ) -> tuple[bool, str]:
        """
        Check if a correction is compatible with version pinning.

        Version pinning ensures that corrections from old prompt versions
        don't generate incorrect signals for new versions.

        Args:
            correction: The correction event
            current_prompt_version: Current active prompt version

        Returns:
            Tuple of (is_compatible, reason)
        """
        # If correction is from current version, it's compatible
        if correction.prompt_version == current_prompt_version:
            return True, "Correction from current version"

        # If correction is from older version, check if it should be ignored
        # This prevents old version errors from biasing new version calibration
        version_diff = self._compare_versions(
            correction.prompt_version, current_prompt_version
        )

        if version_diff > 1:  # More than 1 major/minor version difference
            return (
                False,
                f"Correction from outdated version: {correction.prompt_version} vs {current_prompt_version}",
            )

        return True, "Correction from compatible version"

    def _compare_versions(self, version_a: str, version_b: str) -> int:
        """
        Compare two semantic versions.

        Returns the difference in version numbers.
        """

        def parse_version(v: str) -> tuple[int, int]:
            # Parse "v2.1" -> (2, 1)
            parts = v.replace("v", "").split(".")
            return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)

        va = parse_version(version_a)
        vb = parse_version(version_b)

        # Calculate difference
        major_diff = abs(va[0] - vb[0])
        minor_diff = abs(va[1] - vb[1])

        return major_diff * 10 + minor_diff

    def filter_corrections_by_version(
        self,
        corrections: Sequence[CorrectionEvent],
        current_prompt_version: str,
    ) -> Sequence[CorrectionEvent]:
        """
        Filter corrections to only include those compatible with version pinning.

        Args:
            corrections: All corrections
            current_prompt_version: Current active prompt version

        Returns:
            Filtered list of compatible corrections
        """
        compatible = []
        for correction in corrections:
            is_compatible, _ = self.check_version_pinning_compatibility(
                correction, current_prompt_version
            )
            if is_compatible:
                compatible.append(correction)

        if len(compatible) < len(corrections):
            logger.info(
                "corrections_filtered_by_version",
                total=len(corrections),
                compatible=len(compatible),
                filtered_out=len(corrections) - len(compatible),
                current_version=current_prompt_version,
            )

        return compatible

    def should_trigger_auto_rollback(
        self,
        parameter: CalibratableParameter,
        recent_correction_rate: float,
        baseline_rate: float,
        threshold: float = 0.2,
    ) -> tuple[bool, str]:
        """
        Determine if automatic rollback should be triggered.

        Triggers rollback if correction rate degrades significantly after update.

        Args:
            parameter: The parameter to check
            recent_correction_rate: Recent correction rate after update
            baseline_rate: Baseline correction rate before update
            threshold: Degradation threshold (default: 20%)

        Returns:
            Tuple of (should_rollback, reason)
        """
        if recent_correction_rate > baseline_rate * (1 + threshold):
            return (
                True,
                f"Correction rate degraded from {baseline_rate:.3f} to {recent_correction_rate:.3f} "
                f"({(recent_correction_rate - baseline_rate) / baseline_rate * 100:.1f}% increase)",
            )

        return False, "Correction rate within acceptable range"

    def create_safety_checkpoint(
        self,
        parameter_id: str,
        current_value: float,
        reason: str = "Pre-update checkpoint",
    ) -> str:
        """
        Create a safety checkpoint before applying updates.

        Returns checkpoint ID.
        """
        checkpoint_id = str(uuid.uuid4())
        logger.info(
            "safety_checkpoint_created",
            checkpoint_id=checkpoint_id,
            parameter_id=parameter_id,
            current_value=current_value,
            reason=reason,
        )
        return checkpoint_id

    def log_calibration_decision(
        self,
        decision: str,
        proposal_id: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a calibration decision for audit trail.

        Args:
            decision: Decision made (approve/reject/rollback)
            proposal_id: ID of the proposal
            reason: Reason for the decision
            metadata: Additional metadata
        """
        logger.info(
            "calibration_decision",
            decision=decision,
            proposal_id=proposal_id,
            reason=reason,
            metadata=metadata or {},
        )
