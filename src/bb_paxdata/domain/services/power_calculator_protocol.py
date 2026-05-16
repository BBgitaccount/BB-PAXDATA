from typing import Protocol

from bb_paxdata.domain.models.power_index import PowerIndex


class PowerCalculatorProtocol(Protocol):
    """Protocol for calculating speaker power indices based on Van Dijk CDA."""

    async def calculate(
        self, text: str, speaker_id: str, segment_id: str
    ) -> PowerIndex:
        """Calculate power index for a given speaker and text."""
        ...
