# src/bb_paxdata/infrastructure/retrieval/meilisearch_keyword_retriever.py
from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

from bb_paxdata.domain.services.protocols.rag_protocols import (
    KeywordRetrieverProtocol,
    RAGQueryRequest,
    RetrievedContext,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)


class MeilisearchKeywordRetriever(KeywordRetrieverProtocol):
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    async def search(self, request: RAGQueryRequest) -> Sequence[RetrievedContext]:
        if not request.query.strip():
            return []

        try:
            filters = []
            if request.panel_id_filter:
                filters.append(f"file_id = '{request.panel_id_filter}'")
            if request.country_filters:
                c_filters = " OR ".join(
                    f"country = '{c}'" for c in request.country_filters
                )
                filters.append(f"({c_filters})")
            if request.speaker_filter:
                filters.append(f"speaker_name = '{request.speaker_filter}'")

            filter_str = " AND ".join(filters) if filters else None

            from bb_paxdata.infrastructure.search.meilisearch_client import (
                search_sentences,
            )

            res = await search_sentences(
                query=request.query,
                filters=filter_str,
                limit=request.top_k_keyword,
            )
            hits = res.get("hits", [])

            results = []
            for hit in hits:
                results.append(
                    RetrievedContext(
                        sentence_id=hit["sent_id"],
                        text=hit.get("sentence_text", hit.get("text", "")),
                        speaker_name=hit.get("speaker_name", ""),
                        country=hit.get("country", ""),
                        panel_id=hit.get("file_id", ""),
                        similarity_score=1.0,
                        retrieval_source="meilisearch",
                    )
                )
            return results

        except Exception as e:
            logger.warning(f"Meilisearch search failed, falling back to SQL: {e}")

            from bb_paxdata.infrastructure.db.models import Sentence as ORMSentence

            stmt = select(ORMSentence)

            if request.panel_id_filter:
                stmt = stmt.where(ORMSentence.file_id == request.panel_id_filter)
            if request.country_filters:
                stmt = stmt.where(ORMSentence.country.in_(request.country_filters))
            if request.speaker_filter:
                stmt = stmt.where(ORMSentence.speaker_name == request.speaker_filter)

            # Perform a case-insensitive LIKE search
            stmt = stmt.where(ORMSentence.text.ilike(f"%{request.query}%"))
            stmt = stmt.limit(request.top_k_keyword)

            async with self._session_factory() as session:
                rows = (await session.execute(stmt)).scalars().all()
                results = [
                    RetrievedContext(
                        sentence_id=r.sent_id,
                        text=r.text,
                        speaker_name=r.speaker_name,
                        country=r.country or "",
                        panel_id=r.file_id,
                        similarity_score=1.0,
                        retrieval_source="meilisearch_fallback",
                    )
                    for r in rows
                ]
                return results
