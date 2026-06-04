# src/bb_paxdata/infrastructure/retrieval/pgvector_dense_retriever.py
from __future__ import annotations

import json
from typing import Any, Callable, Sequence

import numpy as np
import structlog
from bb_paxdata.domain.services.protocols.rag_protocols import (
    DenseRetrieverProtocol,
    RAGQueryRequest,
    RetrievedContext,
)
from bb_paxdata.infrastructure.nlp.sbert_embedding_service import SBERTEmbeddingService
from sqlalchemy import select, text

logger = structlog.get_logger()


class PgvectorDenseRetriever(DenseRetrieverProtocol):
    def __init__(
        self,
        session_factory: Callable[[], Any],
        embedding_service: SBERTEmbeddingService,
        embedding_dim: int = 384,
    ) -> None:
        self._session_factory = session_factory
        self._embed = embedding_service
        self._dim = embedding_dim

    async def search(self, request: RAGQueryRequest) -> Sequence[RetrievedContext]:
        if not request.query.strip():
            return []

        vector_arr = (await self._embed.get_embeddings([request.query]))[0]
        vector: list[float] = vector_arr.tolist()

        # Determine dialect
        is_postgresql = True
        try:
            async with self._session_factory() as session:
                dialect_name = session.bind.dialect.name
                is_postgresql = dialect_name == "postgresql"
        except Exception:
            is_postgresql = False

        if is_postgresql:
            # Build dynamic filter CTE for deterministic query planning
            filters = ["embedding IS NOT NULL"]
            params: dict[str, object] = {
                "query_vec": str(vector),  # pgvector accepts text cast
                "dim": self._dim,
                "limit": request.top_k_dense,
            }

            if request.panel_id_filter:
                filters.append("file_id = :panel_id")
                params["panel_id"] = request.panel_id_filter

            if request.country_filters:
                placeholders = [
                    f":country_{i}" for i in range(len(request.country_filters))
                ]
                filters.append(f"country = ANY(ARRAY[{','.join(placeholders)}])")
                for i, c in enumerate(request.country_filters):
                    params[f"country_{i}"] = c

            if request.speaker_filter:
                filters.append("speaker_name = :speaker_filter")
                params["speaker_filter"] = request.speaker_filter

            where_clause = " AND ".join(filters)

            sql = text(
                f"""
                SELECT
                    sent_id,
                    text,
                    speaker_name,
                    country,
                    file_id AS panel_id,
                    1 - (embedding <=> CAST(:query_vec AS vector(:dim))) AS similarity
                FROM sentences
                WHERE {where_clause}
                ORDER BY embedding <=> CAST(:query_vec AS vector(:dim))
                LIMIT :limit
            """
            )

            async with self._session_factory() as session:
                rows = await session.execute(sql, params)
                results = [
                    RetrievedContext(
                        sentence_id=r.sent_id,
                        text=r.text,
                        speaker_name=r.speaker_name,
                        country=r.country or "",
                        panel_id=r.panel_id,
                        similarity_score=float(r.similarity or 0.0),
                        retrieval_source="pgvector",
                    )
                    for r in rows.mappings()
                ]
        else:
            # SQLite fallback: load matching sentences and compute similarity in Python
            from bb_paxdata.infrastructure.db.models import Sentence as ORMSentence

            stmt = select(ORMSentence)
            if request.panel_id_filter:
                stmt = stmt.where(ORMSentence.file_id == request.panel_id_filter)
            if request.country_filters:
                stmt = stmt.where(ORMSentence.country.in_(request.country_filters))
            if request.speaker_filter:
                stmt = stmt.where(ORMSentence.speaker_name == request.speaker_filter)

            async with self._session_factory() as session:
                rows = (await session.execute(stmt)).scalars().all()

                if not rows:
                    return []

                texts_to_embed = []
                indices_to_embed = []
                sentence_embeddings: list[np.ndarray | None] = []

                for idx, r in enumerate(rows):
                    emb = r.embedding
                    if emb is not None:
                        if isinstance(emb, str):
                            try:
                                emb = json.loads(emb)
                            except Exception:
                                pass
                        sentence_embeddings.append(np.array(emb, dtype=np.float32))
                    else:
                        texts_to_embed.append(r.text)
                        indices_to_embed.append(idx)
                        sentence_embeddings.append(None)

                if texts_to_embed:
                    computed_vectors = await self._embed.get_embeddings(texts_to_embed)
                    for vec, idx in zip(computed_vectors, indices_to_embed):
                        sentence_embeddings[idx] = vec

                target_np = np.array(vector, dtype=np.float32)
                target_norm = np.linalg.norm(target_np)

                scored_rows = []
                for r, emb in zip(rows, sentence_embeddings):
                    if emb is not None and target_norm > 0:
                        emb_norm = np.linalg.norm(emb)
                        if emb_norm > 0:
                            sim = float(
                                np.dot(emb, target_np) / (emb_norm * target_norm)
                            )
                        else:
                            sim = 0.0
                    else:
                        sim = 0.0
                    scored_rows.append((r, sim))

                scored_rows.sort(key=lambda x: x[1], reverse=True)
                results = [
                    RetrievedContext(
                        sentence_id=r.sent_id,
                        text=r.text,
                        speaker_name=r.speaker_name,
                        country=r.country or "",
                        panel_id=r.file_id,
                        similarity_score=sim,
                        retrieval_source="pgvector_fallback",
                    )
                    for r, sim in scored_rows[: request.top_k_dense]
                ]

        logger.info(
            "pgvector_dense_search",
            query_prefix=request.query[:60],
            hits=len(results),
            top_similarity=results[0].similarity_score if results else None,
        )
        return results
