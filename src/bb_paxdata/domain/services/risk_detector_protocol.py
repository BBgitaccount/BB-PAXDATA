from collections.abc import Sequence
from typing import Protocol

from bb_paxdata.domain.models.risk_signal import RiskSignal


class RiskSignalDetectorProtocol(Protocol):
    """Protocol for detecting risk signals in diplomatic discourse."""

    async def detect(self, text: str, sentence_id: str) -> Sequence[RiskSignal]:
        """Detect risk signals in the given text."""
        ...
