from typing import Protocol

from bb_paxdata.application.domain.models.speech_act import SpeechActClassification


class SpeechActClassifierProtocol(Protocol):
    """Protocol defining the interface for speech act classification services."""

    async def classify(
        self, text: str, srl_context: dict | None = None
    ) -> SpeechActClassification:
        """Classifies the primary and secondary speech acts of the given text.

        Args:
            text: The text content to analyze.
            srl_context: Optional PropBank semantic role labeling context.

        Returns:
            SpeechActClassification result.
        """
        ...
