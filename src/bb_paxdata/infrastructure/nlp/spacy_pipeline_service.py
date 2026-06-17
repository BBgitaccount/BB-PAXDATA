"""
SpaCy Pipeline Service for BB-PAXDATA — Infrastructure implementation.

Provides high-level wrappers for processing text and batches using SpaCy.
Infrastructure implementation of ISpacyPipelineService Protocol.
"""

from __future__ import annotations

from collections.abc import Iterable

import structlog
from spacy.tokens import Doc

from bb_paxdata.application.domain.models.srl import (
    ExtractionStatus,
    SRLDocumentResult,
    SRLFrame,
)
from bb_paxdata.application.domain.ports.i_spacy_pipeline import ISpacyPipelineService
from bb_paxdata.infrastructure.nlp.spacy_manager import SpacyModelManager
from bb_paxdata.infrastructure.nlp.srl_pipeline import get_srl_pipeline

logger = structlog.get_logger(__name__)


class SpacyPipelineService:
    """
    Infrastructure implementation of ISpacyPipelineService.
    Service wrapper for SpaCy processing.
    """

    @staticmethod
    def process_text(text: str, lang: str) -> Doc:
        """
        Process a single text string.

        Args:
            text: The text to process.
            lang: Language code for model selection.

        Returns:
            A SpaCy Doc object.
        """
        nlp = SpacyModelManager.get_model(lang)
        return nlp(text)

    @staticmethod
    def process_batch(
        texts: Iterable[str], lang: str, batch_size: int = 50
    ) -> list[Doc]:
        """
        Process a batch of texts efficiently using nlp.pipe().

        Args:
            texts: An iterable of text strings.
            lang: Language code for model selection.
            batch_size: Number of texts to process per batch.

        Returns:
            A list of SpaCy Doc objects.
        """
        nlp = SpacyModelManager.get_model(lang)
        return list(nlp.pipe(texts, batch_size=batch_size))

    @staticmethod
    def extract_semantic_roles_enhanced(doc: Doc) -> SRLDocumentResult:
        """
        Enhanced SRL extraction using production pipeline.

        Features:
        - Automatic fallback on failure
        - Per-sentence granularity
        - Status tracking
        - Error isolation (one failure doesn't stop others)

        Args:
            doc: spaCy processed Doc object

        Returns:
            SRLDocumentResult with frames mapped to sentence indices
        """
        srl_pipeline = get_srl_pipeline()
        all_frames: list[SRLFrame] = []
        processed_count = 0
        failed_count = 0

        # We process each sentence in the Doc
        for sent_idx, sent in enumerate(doc.sents):
            try:
                # Extract SRL for individual sentence
                result = srl_pipeline.extract_from_text(sent.text)

                # Annotate frames with source sentence index
                for frame in result.frames:
                    frame.source_sentence_idx = sent_idx

                all_frames.extend(result.frames)
                processed_count += 1

                # Update sentence-level status if custom user attributes are supported
                if hasattr(sent, "_"):
                    try:
                        sent._.srl_frames = result.frames
                        sent._.srl_extraction_status = ExtractionStatus.COMPLETED
                    except AttributeError:
                        pass

            except Exception as e:
                failed_count += 1
                logger.warning(f"SRL extraction failed for sentence {sent_idx}: {e}")
                if hasattr(sent, "_"):
                    try:
                        sent._.srl_frames = []
                        sent._.srl_extraction_status = ExtractionStatus.FAILED
                    except AttributeError:
                        pass
                continue

        return SRLDocumentResult(
            frames=all_frames,
            total_sentences_processed=processed_count + failed_count,
            total_frames_extracted=len(all_frames),
        )

    @staticmethod
    def extract_semantic_roles_legacy(doc: Doc) -> list[SRLFrame]:
        """
        Legacy interface for backward compatibility.
        Delegates to enhanced version but returns flat list.
        """
        result = SpacyPipelineService.extract_semantic_roles_enhanced(doc)
        return result.frames


# Backward-compatibility alias
SpacyPipeline = SpacyPipelineService

# Port conformance guard
_stub = SpacyPipelineService.__new__(SpacyPipelineService)
assert isinstance(
    _stub, ISpacyPipelineService
), "SpacyPipelineService must satisfy ISpacyPipelineService"
del _stub
