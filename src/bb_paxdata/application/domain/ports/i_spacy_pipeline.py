from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.srl import SRLDocumentResult, SRLFrame
    from spacy.tokens import Doc


@runtime_checkable
class ISpacyPipelineService(Protocol):
    """Domain port for spaCy text processing.

    Concrete implementation:
        src/bb_paxdata/infrastructure/nlp/spacy_pipeline_service.py

    Used by: PresuppositionService, argument_structure_pipeline, NegationDetector.
    """

    def process_text(self, text: str, lang: str) -> Doc:
        """Parse a single text and return a spaCy Doc."""
        ...

    def process_batch(
        self, texts: Iterable[str], lang: str, batch_size: int = 50
    ) -> list[Doc]:
        """Batch-process texts via nlp.pipe()."""
        ...

    def extract_semantic_roles_enhanced(self, doc: Doc) -> SRLDocumentResult:
        """Per-sentence SRL extraction with fallback and status tracking."""
        ...

    def extract_semantic_roles_legacy(self, doc: Doc) -> list[SRLFrame]:
        """Legacy SRL interface — returns flat SRLFrame list."""
        ...
