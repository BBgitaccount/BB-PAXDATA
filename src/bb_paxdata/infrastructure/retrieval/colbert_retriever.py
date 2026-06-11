from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    RAGQueryRequest,
    RetrievedContext,
)
from bb_paxdata.infrastructure.nlp.colbert_service import RAGatoulleColBERTService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ColBERTDenseRetriever:
    """
    DenseRetrieverProtocol implementation backed by RAGatoulleColBERTService.
    Adapts ragatouille search results to RetrievedContext domain objects.
    """

    def __init__(
        self,
        colbert_service: RAGatoulleColBERTService,  # TODO(MİMARİ-5): -> ColBERTEmbeddingServiceProtocol
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._colbert = colbert_service
        self._session_factory = session_factory

    async def search(self, request: RAGQueryRequest) -> list[RetrievedContext]:
        """
        Perform late-interaction MaxSim retrieval using ColBERT PLAID.

        Args:
            request: RAG query request with query text and retrieval parameters.

        Returns:
            List of RetrievedContext objects ordered by descending MaxSim score.
        """
        # ragatouille.search() is synchronous — run in thread pool
        loop = asyncio.get_running_loop()
        raw_results = await loop.run_in_executor(
            None,
            lambda: self._colbert.retrieve(query=request.query, k=request.top_k_dense),
        )

        # Map ragatouille results to RetrievedContext
        # Note: ragatouille returns {"content": str, "document_id": str, "score": float}
        # We need to map this to RetrievedContext which requires sentence_id, text, speaker_name, country, panel_id
        # Since ColBERT operates on pre-indexed passages, we'll need to parse the document_id
        # to extract the original sentence/segment information
        contexts = []
        for r in raw_results:
            # Parse document_id to extract metadata
            # Expected format: "segment:{segment_id}" or "sentence:{sentence_id}"
            doc_id = r.get("document_id", "")
            content = r.get("content", "")
            score = float(r.get("score", 0.0))

            # Post-retrieval DB lookup to populate metadata fields
            speaker_name = None
            country = None
            panel_id = None

            if doc_id.startswith("sentence:") and self._session_factory is not None:
                sent_id = doc_id.split(":", 1)[1]
                async with self._session_factory() as session:
                    from bb_paxdata.infrastructure.db.repositories.sentence import (
                        SentenceRepository,
                    )

                    sentence_repo = SentenceRepository(session)
                    sentence = await sentence_repo.get(sent_id)
                    if sentence:
                        speaker_name = sentence.speaker_name
                        country = sentence.country
                        panel_id = sentence.file_id

            contexts.append(
                RetrievedContext(
                    sentence_id=doc_id,
                    text=content,
                    speaker_name=speaker_name,
                    country=country,
                    panel_id=panel_id,
                    similarity_score=score,
                    retrieval_source="colbert_plaid",
                )
            )

        return contexts
