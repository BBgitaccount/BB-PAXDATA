"""
Consensus Moment Domain Models
CORRECTED (E05-M-02, E05-M-03): Fixed stability type ambiguity and clarified panel_range.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class CoalitionCluster:
    """
    Coalition cluster from DBSCAN clustering of speaker positions.

    CORRECTED (E05-M-02): Stability expressed as BOTH raw count and normalized fraction.
    """

    cluster_id: str
    members: list[str]
    centroid_theta: float
    time_range: tuple[datetime, datetime]

    # CORRECTED (E05-M-02): Stability expressed as BOTH raw count and normalized fraction
    stable_session_count: int = 0  # how many sessions this cluster persisted unchanged
    stability: float = 0.0  # = stable_session_count / window_size, range [0.0, 1.0]
    window_size: int = 3  # denominator for stability — the rolling window size

    def __post_init__(self) -> None:
        """Compute stability from stable_session_count and window_size."""
        if self.window_size <= 0:
            raise ValueError("window_size must be positive")
        object.__setattr__(
            self, "stability", self.stable_session_count / self.window_size
        )


@dataclass
class ConsensusMoment:
    """
    Consensus/divergence moment in positional tracking.

    CORRECTED (E05-M-03): Clarified panel_range to session_range for unambiguous semantics.
    """

    speakers: list[str]
    topic: str | None = None

    # CORRECTED (E05-M-03): session_range is indexed by session, not arbitrary datetime window
    session_range: tuple[str, str] = field(
        default_factory=lambda: ("", "")
    )  # (session_id_start, session_id_end) — unambiguous
    session_timestamps: tuple[datetime, datetime] = field(
        default_factory=lambda: (datetime.min, datetime.min)
    )  # for display/reporting only

    convergence_type: Literal["convergence", "divergence", "stable"] = "stable"
    confidence: float = 0.5  # from Bayesian CI width (requires FINDING I-02 fix)
    theta_spread: float = 0.0  # max(theta) - min(theta) at this moment
    delta_theta_spread: float = 0.0  # theta_spread(t) - theta_spread(t-1) — signed
