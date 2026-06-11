from typing import Any, Protocol, runtime_checkable

from bb_paxdata.application.domain.models.negation_cue import (
    LanguageCode,
    NegationResult,
)


@runtime_checkable
class NegationDetector(Protocol):
    """Domain port interface for negation detection services."""

    async def detect(
        self, text: str, sentence_id: str, language: str | None = None
    ) -> NegationResult:
        """Detect negation cues, types, and scopes in the given text."""
        ...

    async def detect_with_doc(
        self, doc: Any, sentence_id: str, language: LanguageCode
    ) -> NegationResult:
        """Detect negation cues on a pre-parsed spaCy doc."""
        ...
