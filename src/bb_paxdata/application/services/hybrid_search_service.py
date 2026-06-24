"""Hybrid search service combining keyword and semantic search using Reciprocal Rank Fusion."""

from collections import defaultdict
from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.repositories.sentence import SentenceRepository
from bb_paxdata.infrastructure.nlp.sbert_embedding_service import SBERTEmbeddingService

logger = structlog.get_logger(__name__)


class HybridSearchService:
    """Service for hybrid search combining keyword and semantic search using RRF."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        embedding_service: SBERTEmbeddingService,
        rrf_k: int = 60,
    ) -> None:
        """
        Initialize hybrid search service.

        Args:
            session_factory: Database session factory
            embedding_service: Embedding service for semantic search
            rrf_k: RRF constant (default 60)
        """
        self._session_factory = session_factory
        self._embed = embedding_service
        self._rrf_k = rrf_k

    async def search(
        self,
        query: str,
        file_id: str | None = None,
        country: str | None = None,
        speaker_name: str | None = None,
        dominant_topic: str | None = None,
        min_risk: int | None = None,
        emotion_category: str | None = None,
        limit: int = 20,
        top_k_keyword: int = 50,
        top_k_dense: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Perform hybrid search using RRF to combine keyword and semantic results.

        Args:
            query: Search query
            file_id: Optional file filter
            country: Optional country filter
            speaker_name: Optional speaker filter
            dominant_topic: Optional topic filter
            min_risk: Minimum risk score filter
            emotion_category: Emotion category filter
            limit: Maximum number of results
            top_k_keyword: Number of keyword results to retrieve
            top_k_dense: Number of semantic results to retrieve

        Returns:
            List of search results with combined RRF scores
        """
        # Perform keyword search (Meilisearch)
        keyword_results = await self._keyword_search(
            query=query,
            file_id=file_id,
            country=country,
            speaker_name=speaker_name,
            dominant_topic=dominant_topic,
            min_risk=min_risk,
            emotion_category=emotion_category,
            limit=top_k_keyword,
        )

        # Perform semantic search (pgvector)
        semantic_results = await self._semantic_search(
            query=query,
            file_id=file_id,
            country=country,
            speaker_name=speaker_name,
            limit=top_k_dense,
        )

        # Apply RRF to combine results
        combined_results = self._apply_rrf(
            keyword_results=keyword_results,
            semantic_results=semantic_results,
            k=self._rrf_k,
        )

        # Sort by RRF score and limit
        combined_results.sort(key=lambda x: x["rrf_score"], reverse=True)
        return combined_results[:limit]

    async def _keyword_search(
        self,
        query: str,
        file_id: str | None = None,
        country: str | None = None,
        speaker_name: str | None = None,
        dominant_topic: str | None = None,
        min_risk: int | None = None,
        emotion_category: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Perform keyword search using Meilisearch."""
        from bb_paxdata.infrastructure.search.meilisearch_client import (
            search_sentences,
        )

        filters = []
        if file_id:
            filters.append(f'file_id = "{file_id}"')
        if country:
            filters.append(f'country = "{country}"')
        if speaker_name:
            filters.append(f'speaker_name = "{speaker_name}"')
        if dominant_topic:
            filters.append(f'dominant_topic = "{dominant_topic}"')
        if min_risk is not None:
            filters.append(f"risk_score >= {min_risk}")
        if emotion_category:
            filters.append(f'emotion_category = "{emotion_category}"')

        filter_str = " AND ".join(filters) if filters else None

        result = await search_sentences(
            query=query,
            filters=filter_str,
            limit=limit,
        )

        hits = result.get("hits", [])
        results = []
        for rank, hit in enumerate(hits, start=1):
            results.append(
                {
                    "sent_id": hit["sent_id"],
                    "text": hit.get("text", ""),
                    "speaker_name": hit.get("speaker_name", ""),
                    "country": hit.get("country", ""),
                    "file_id": hit.get("file_id", ""),
                    "dominant_topic": hit.get("dominant_topic", ""),
                    "risk_score": hit.get("risk_score", 0),
                    "emotion_category": hit.get("emotion_category", ""),
                    "keyword_rank": rank,
                    "semantic_rank": None,
                }
            )

        logger.info(
            "keyword_search_completed",
            query=query[:50],
            hits=len(results),
        )
        return results

    async def _semantic_search(
        self,
        query: str,
        file_id: str | None = None,
        country: str | None = None,
        speaker_name: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Perform semantic search using pgvector."""
        # Get query embedding
        vector_arr = (await self._embed.get_embeddings([query]))[0]
        query_vector = vector_arr.tolist()

        async with self._session_factory() as session:
            repo = SentenceRepository(session=session)
            results = await repo.search_by_vector(
                query_vector=query_vector,
                file_id=file_id,
                country=country,
                speaker_name=speaker_name,
                limit=limit,
            )

        semantic_results = []
        for rank, (sent, score) in enumerate(results, start=1):
            semantic_results.append(
                {
                    "sent_id": sent.sent_id,
                    "text": sent.text,
                    "speaker_name": sent.speaker_name or "",
                    "country": sent.country or "",
                    "file_id": sent.file_id,
                    "dominant_topic": sent.dominant_topic or "",
                    "risk_score": sent.risk_score or 0,
                    "emotion_category": sent.emotion_category or "",
                    "keyword_rank": None,
                    "semantic_rank": rank,
                    "similarity_score": score,
                }
            )

        logger.info(
            "semantic_search_completed",
            query=query[:50],
            hits=len(semantic_results),
        )
        return semantic_results

    def _apply_rrf(
        self,
        keyword_results: list[dict[str, Any]],
        semantic_results: list[dict[str, Any]],
        k: int = 60,
    ) -> list[dict[str, Any]]:
        """
        Apply Reciprocal Rank Fusion to combine keyword and semantic results.

        RRF formula: score = sum(1 / (k + rank)) for each result

        Args:
            keyword_results: Results from keyword search with ranks
            semantic_results: Results from semantic search with ranks
            k: RRF constant

        Returns:
            Combined results with RRF scores
        """
        # Create a map of sent_id to combined scores
        score_map = defaultdict(lambda: {"rrf_score": 0.0, "data": {}})

        # Add keyword scores
        for result in keyword_results:
            sent_id = result["sent_id"]
            rank = result["keyword_rank"]
            score = 1.0 / (k + rank)
            score_map[sent_id]["rrf_score"] += score
            score_map[sent_id]["data"] = result

        # Add semantic scores
        for result in semantic_results:
            sent_id = result["sent_id"]
            rank = result["semantic_rank"]
            score = 1.0 / (k + rank)
            if sent_id in score_map:
                score_map[sent_id]["rrf_score"] += score
                # Merge data if needed
                if result.get("similarity_score"):
                    score_map[sent_id]["data"]["similarity_score"] = result[
                        "similarity_score"
                    ]
            else:
                score_map[sent_id]["rrf_score"] = score
                score_map[sent_id]["data"] = result

        # Convert to list
        combined = []
        for sent_id, item in score_map.items():
            combined.append(
                {
                    **item["data"],
                    "rrf_score": item["rrf_score"],
                }
            )

        logger.info(
            "rrf_applied",
            keyword_results=len(keyword_results),
            semantic_results=len(semantic_results),
            combined=len(combined),
        )
        return combined

    async def get_facets(
        self,
        query: str | None = None,
        file_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get facet counts for filters.

        Args:
            query: Optional search query to facet within
            file_id: Optional file filter

        Returns:
            Dictionary with facet counts for countries, speakers, topics, emotions
        """
        from bb_paxdata.infrastructure.search.meilisearch_client import (
            search_sentences,
        )

        filters = []
        if file_id:
            filters.append(f'file_id = "{file_id}"')

        filter_str = " AND ".join(filters) if filters else None

        # Search with facets
        result = await search_sentences(
            query=query or "",
            filters=filter_str,
            limit=0,  # We only need facet counts
        )

        # Extract facet distribution if available
        facets = result.get("facetDistribution", {})

        return {
            "countries": facets.get("country", {}),
            "speakers": facets.get("speaker_name", {}),
            "topics": facets.get("dominant_topic", {}),
            "emotions": facets.get("emotion_category", {}),
        }
