from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from bb_paxdata.application.domain.services.colbert_embedding_service import (
    RAGatoulleColBERTService,
)
from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    RAGQueryRequest,
    RetrievedContext,
)

if TYPE_CHECKING:
    pass


class ColBERTDenseRetriever:
    """
    DenseRetrieverProtocol implementation backed by RAGatoulleColBERTService.
    Adapts ragatouille search results to RetrievedContext domain objects.
    """

    def __init__(self, colbert_service: RAGatoulleColBERTService) -> None:
        self._colbert = colbert_service

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

            # ColBERT PLAID index doesn't store metadata; fields are None
            # Future enhancement: fetch metadata from DB using document_id
            contexts.append(
                RetrievedContext(
                    sentence_id=doc_id,
                    text=content,
                    speaker_name=None,
                    country=None,
                    panel_id=None,
                    similarity_score=score,
                    retrieval_source="colbert_plaid",
                )
            )

        return contexts
