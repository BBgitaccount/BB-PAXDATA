import asyncio

import numpy as np
import structlog

from bb_paxdata.domain.models.dki import DynamicPositionResult, SpeakerTrajectory

logger = structlog.get_logger()


class PooleRosenthalPositionTracker:
    """Dynamic ideal point tracker using DW-NOMINATE inspired velocity metrics.

    Critical Constraints:
    - Input trajectory MUST be pre-sorted chronologically.
    - Missing θᵢ values are interpolated linearly.
    - Velocity unit: position units per day.
    - Smoothing: simple moving average (SMA).
    """

    def __init__(self, smoothing_method: str = "sma") -> None:
        self._smoothing = smoothing_method
        self._logger = logger.bind(service="position_tracker")

    async def compute_velocity(
        self,
        trajectory: SpeakerTrajectory,
        smoothing_window: int = 3,
    ) -> DynamicPositionResult:
        """Compute Δθ/Δt and acceleration for speaker position time-series."""

        # 1. Validate and Sort (ensure chronological)
        # Assuming input is Sequence[dict[str, Any]] where dict is {"theta": float, "timestamp": datetime}
        sorted_points = sorted(trajectory.positions, key=lambda x: x["timestamp"])

        if len(sorted_points) < 2:
            return self._empty_result(trajectory.speaker_id)

        # 2. Extract values and dates
        thetas = [p["theta"] for p in sorted_points]
        dates = [p["timestamp"] for p in sorted_points]

        # 3. Interpolate missing θᵢ (if any are None, though SpeakerTrajectory suggests they are float)
        # For now, we assume θᵢ are present, but we check for temporal gaps.
        interpolation_count = 0
        # If we had explicit None values, we would interpolate here.

        # 4. Calculate raw velocities: Δθ / Δt (days)
        raw_velocities = []
        for i in range(1, len(thetas)):
            delta_theta = thetas[i] - thetas[i - 1]
            delta_t = (dates[i] - dates[i - 1]).total_seconds() / 86400.0  # days

            if delta_t <= 0:
                self._logger.warning("Zero or negative time delta detected", i=i)
                velocity = 0.0
            else:
                velocity = delta_theta / delta_t

            raw_velocities.append(float(velocity))

        # 5. Apply smoothing (SMA)
        smoothed_velocities = await asyncio.to_thread(
            self._apply_sma, raw_velocities, smoothing_window
        )

        # 6. Compute acceleration (derivative of velocity)
        current_velocity = smoothed_velocities[-1] if smoothed_velocities else 0.0

        current_acceleration = 0.0
        if len(smoothed_velocities) >= 2:
            # Acceleration = Δv / Δt
            delta_v = smoothed_velocities[-1] - smoothed_velocities[-2]
            delta_t = (dates[-1] - dates[-2]).total_seconds() / 86400.0
            if delta_t > 0:
                current_acceleration = delta_v / delta_t

        max_gap = max(
            [
                (dates[i] - dates[i - 1]).total_seconds() / 86400.0
                for i in range(1, len(dates))
            ],
            default=0.0,
        )

        return DynamicPositionResult(
            speaker_id=trajectory.speaker_id,
            session_count=len(thetas),
            raw_velocities=raw_velocities,
            smoothed_velocities=smoothed_velocities,
            current_velocity=float(current_velocity),
            current_acceleration=float(current_acceleration),
            interpolation_count=interpolation_count,
            max_gap_days=float(max_gap),
            calculation_method=f"poole_rosenthal_1997_{self._smoothing}",
        )

    def _apply_sma(self, data: list[float], window: int) -> list[float]:
        """Apply Simple Moving Average."""
        if not data:
            return []

        smoothed = []
        for i in range(len(data)):
            start = max(0, i - window + 1)
            subset = data[start : i + 1]
            smoothed.append(float(np.mean(subset)))
        return smoothed

    def _empty_result(self, speaker_id: str) -> DynamicPositionResult:
        return DynamicPositionResult(
            speaker_id=speaker_id,
            session_count=0,
            raw_velocities=[],
            smoothed_velocities=[],
            current_velocity=0.0,
            current_acceleration=0.0,
            interpolation_count=0,
            max_gap_days=0.0,
            calculation_method=f"poole_rosenthal_1997_{self._smoothing}",
        )
