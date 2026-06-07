"""
Bayesian Dynamic Position Adapter for TASK-A07.

This module provides an adapter that bridges BayesianPositionTracker with the
DynamicPositionTracker protocol, enabling Bayesian tracking within the existing
DKI pipeline architecture.

MAJOR FIX (FINDING M-04): Implements DynamicPositionTracker protocol via adapter
pattern instead of creating a parallel protocol. Maintains per-speaker tracker
state internally with thread-safe access.

Reference: TASK-A07 Finding M-04
"""

from __future__ import annotations

import asyncio
import threading
from typing import Literal

from bb_paxdata.application.domain.models.dki import (
    DynamicPositionResult,
    SpeakerTrajectory,
)
from bb_paxdata.application.domain.services.bayesian_position_tracker import (
    BayesianPositionTracker,
)


class BayesianDynamicPositionAdapter:
    """
    Adapts BayesianPositionTracker to the DynamicPositionTracker protocol.

    Maintains per-speaker tracker state internally. Implements compute_velocity()
    by running Bayesian updates on trajectory points and computing velocity as
    the posterior mean derivative.

    Thread-safe via threading.Lock for per-speaker tracker access.

    Reference: TASK-A07 Finding M-04
    """

    def __init__(
        self,
        filter_type: Literal["kalman", "particle"] = "particle",
        particle_count: int = 1000,
        process_noise: float = 0.1,
    ) -> None:
        """
        Initialize the adapter.

        Args:
            filter_type: "kalman" or "particle" (default "particle")
            particle_count: Number of particles for particle filter
            process_noise: Process noise parameter
        """
        self._trackers: dict[str, BayesianPositionTracker] = {}
        self._lock = threading.Lock()
        self._filter_type = filter_type
        self._particle_count = particle_count
        self._process_noise = process_noise

    async def compute_velocity(
        self,
        trajectory: SpeakerTrajectory,
        smoothing_window: int = 3,
    ) -> DynamicPositionResult:
        """
        Compute velocity using Bayesian position tracking.

        Runs Bayesian updates in thread pool (CPU-bound particle ops) and
        computes velocity as the posterior mean derivative.

        Args:
            trajectory: Speaker trajectory with positions
            smoothing_window: Smoothing window size (currently unused, kept for
                            protocol compatibility)

        Returns:
            DynamicPositionResult with velocity and acceleration
        """
        # Run Bayesian updates in thread pool (CPU-bound particle ops)
        return await asyncio.get_event_loop().run_in_executor(
            None, self._compute_velocity_sync, trajectory, smoothing_window
        )

    def _compute_velocity_sync(
        self, trajectory: SpeakerTrajectory, smoothing_window: int
    ) -> DynamicPositionResult:
        """
        Synchronous implementation of velocity computation.

        Args:
            trajectory: Speaker trajectory
            smoothing_window: Smoothing window (unused in current implementation)

        Returns:
            DynamicPositionResult
        """
        with self._lock:
            # Get or create tracker for this speaker
            tracker = self._trackers.setdefault(
                trajectory.speaker_id,
                BayesianPositionTracker(
                    speaker_id=trajectory.speaker_id,
                    filter_type=self._filter_type,
                    particle_count=self._particle_count,
                    process_noise=self._process_noise,
                ),
            )

        # Run Bayesian updates on each trajectory point
        posterior_means = []
        raw_velocities = []

        for i, pt in enumerate(trajectory.positions):
            # Extract observation and optional metadata
            theta = pt.get("theta", 0.0)
            signal_strength = pt.get("signal_strength", 0.5)
            delta_t_days = pt.get("delta_t_days", 1.0)

            # Update tracker
            result = tracker.update(
                observation=theta,
                signal_strength=signal_strength,
                delta_t_days=delta_t_days,
            )
            posterior_means.append(result.posterior_mean)

            # Compute raw velocity (finite difference)
            if i > 0:
                velocity = posterior_means[i] - posterior_means[i - 1]
                raw_velocities.append(velocity)
            else:
                raw_velocities.append(0.0)

        # Compute smoothed velocities (simple moving average)
        if len(raw_velocities) >= smoothing_window:
            smoothed_velocities = [
                sum(raw_velocities[max(0, i - smoothing_window + 1) : i + 1])
                / min(smoothing_window, i + 1)
                for i in range(len(raw_velocities))
            ]
        else:
            smoothed_velocities = raw_velocities.copy()

        # Current velocity and acceleration
        if len(posterior_means) >= 2:
            current_velocity = posterior_means[-1] - posterior_means[-2]
            acceleration = (
                (posterior_means[-1] - 2 * posterior_means[-2] + posterior_means[-3])
                if len(posterior_means) >= 3
                else 0.0
            )
        else:
            current_velocity = 0.0
            acceleration = 0.0

        # Calculate max gap in days
        timestamps = [
            pt.get("timestamp") for pt in trajectory.positions if "timestamp" in pt
        ]
        max_gap_days = 0.0
        if timestamps and len(timestamps) >= 2:
            gaps = [
                (timestamps[i] - timestamps[i - 1]).total_seconds() / 86400.0
                for i in range(1, len(timestamps))
            ]
            max_gap_days = max(gaps) if gaps else 0.0

        return DynamicPositionResult(
            speaker_id=trajectory.speaker_id,
            session_count=len(trajectory.positions),
            raw_velocities=raw_velocities,
            smoothed_velocities=smoothed_velocities,
            current_velocity=current_velocity,
            current_acceleration=acceleration,
            interpolation_count=0,  # No interpolation in Bayesian approach
            max_gap_days=max_gap_days,
            calculation_method="bayesian_morrow_1994",
        )
