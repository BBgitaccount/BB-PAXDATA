"""
Consensus Tracker Use Case
CORRECTED (E05-M-01): Separate use case, not extension of aggregate_bilateral_sentiment.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from bb_paxdata.application.domain.models.consensus_moment import (
    CoalitionCluster,
    ConsensusMoment,
)
from bb_paxdata.application.domain.services.consensus_tracker import (
    IConsensusTrackerService,
)


@dataclass(frozen=True)
class ConsensusTrackerInput:
    """Input data for consensus tracking."""

    session_ids: list[str]
    time_window_sessions: int = 3  # rolling window for stability


@dataclass(frozen=True)
class ConsensusTrackerOutput:
    """Output data from consensus tracking."""

    moments: list[ConsensusMoment]
    clusters: list[CoalitionCluster]
    computed_at: datetime


@dataclass
class ConsensusTrackerUseCase:
    """
    CORRECTED (E05-M-01): Separate use case for consensus tracking.

    NOT an extension of aggregate_bilateral_sentiment.py to avoid SRP violation
    and transaction boundary issues.
    """

    def __init__(
        self,
        tracker_service: IConsensusTrackerService,
    ) -> None:
        self._tracker = tracker_service

    async def execute(
        self, input_data: ConsensusTrackerInput
    ) -> ConsensusTrackerOutput:
        """
        Execute consensus tracking for the given sessions.

        This is triggered after aggregate_bilateral_sentiment.py completes
        to avoid coupling sentiment rebuilding with positional tracking.
        """
        # In a full implementation, this would:
        # 1. Fetch SpeakerPosition data for the sessions
        # 2. Call tracker_service.detect_convergence()
        # 3. Call tracker_service.detect_coalitions()
        # 4. Return the results

        # For now, return empty results as placeholder
        return ConsensusTrackerOutput(
            moments=[],
            clusters=[],
            computed_at=datetime.now(timezone.utc),
        )
