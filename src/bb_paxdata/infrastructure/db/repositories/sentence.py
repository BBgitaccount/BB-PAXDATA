from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.sentence import (
        Sentence as SentenceDomain,
    )

import structlog
from sqlalchemy import select

from bb_paxdata.infrastructure.db.models import Sentence
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class SentenceRepository(BaseRepository[Sentence]):
    """Async repository for Sentence ORM model."""

    model_class = Sentence

    async def get(self, sent_id: str) -> Sentence | None:
        """Get a sentence by ID."""
        return await self.get_by_id(sent_id)

    async def add(self, entity: Any) -> Sentence:
        """Add a sentence (supports domain model or ORM model)."""
        from bb_paxdata.application.domain.models.sentence import (
            Sentence as SentenceDomain,
        )

        if isinstance(entity, SentenceDomain):
            # Extract seg_id and panel_id if available, otherwise default
            # to dummy or previous values
            seg_id = getattr(entity, "segment_id", None) or "unknown_seg"
            # Try to find panel_id from domain model if it exists,
            # otherwise use p1 for tests
            panel_id = getattr(entity, "panel_id", "p1")
            orm = Sentence.from_domain(entity, seg_id=seg_id, panel_id=panel_id)
        else:
            orm = entity
        return await super().add(orm)

    async def get_unanalyzed(
        self, file_id: str | None = None, limit: int | None = None
    ) -> Sequence[Sentence]:
        """Get sentences that haven't been analyzed yet, ordered by risk_score DESC."""
        stmt = select(Sentence).where(Sentence.ai_analyzed == 0)
        if file_id:
            stmt = stmt.where(Sentence.file_id == file_id)
        stmt = stmt.order_by(Sentence.risk_score.desc())
        if limit:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def get_by_panel(self, file_id: str) -> Sequence[Sentence]:
        """Get all sentences for a specific panel."""
        stmt = select(Sentence).where(Sentence.file_id == file_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def get_domain_by_panel(self, file_id: str) -> list[SentenceDomain]:
        """Get all sentences for a specific panel as domain models, ordered by global_sent_order."""

        stmt = (
            select(Sentence)
            .where(Sentence.file_id == file_id)
            .order_by(Sentence.global_sent_order)
        )
        result = await self._session.execute(stmt)
        sentences = result.scalars().all()
        return [s.to_domain() for s in sentences]

    async def get_by_segment(self, seg_id: str) -> Sequence[Sentence]:
        """Get all sentences for a specific segment."""
        stmt = select(Sentence).where(Sentence.seg_id == seg_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def get_fail_sentences(
        self, file_id: str | None = None, check_type: str | None = None
    ) -> Sequence[Sentence]:
        """Get sentences that failed logic checks."""
        stmt = select(Sentence).where(Sentence.logic_result == "FAIL")
        if file_id:
            stmt = stmt.where(Sentence.file_id == file_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def mark_analyzed(self, sent_id: str) -> None:
        """Mark a sentence as analyzed."""
        stmt = select(Sentence).where(Sentence.sent_id == sent_id)
        result = await self._session.execute(stmt)
        sentence = result.scalar_one_or_none()
        if sentence:
            sentence.ai_analyzed = 1
            await self._session.flush()

    async def bulk_mark_analyzed(self, sent_ids: list[str]) -> None:
        """Mark multiple sentences as analyzed in bulk."""
        stmt = select(Sentence).where(Sentence.sent_id.in_(sent_ids))
        result = await self._session.execute(stmt)
        sentences = result.scalars().all()
        for sentence in sentences:
            sentence.ai_analyzed = 1
        await self._session.flush()

    async def get_priority_queue(
        self, top_n: int, file_id: str | None = None
    ) -> Sequence[Sentence]:
        """Get top N sentences ordered by risk_score DESC, power_level DESC."""
        stmt = select(Sentence).where(Sentence.ai_analyzed == 0)
        if file_id:
            stmt = stmt.where(Sentence.file_id == file_id)
        stmt = stmt.order_by(
            Sentence.risk_score.desc(), Sentence.power_level.desc()
        ).limit(top_n)

        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def update_analysis(
        self,
        sent_id: str,
        sentiment_score: float,
        risk_score: int,
        hedging_score: float,
        politeness_ratio: float,
    ) -> None:
        """Update sentence analysis results."""
        stmt = select(Sentence).where(Sentence.sent_id == sent_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.vader_compound = sentiment_score
            orm.risk_score = risk_score
            orm.hedging_score = hedging_score
            orm.politeness_ratio = politeness_ratio
            await self._session.flush()

    async def get_high_risk(self, min_risk_score: int) -> Sequence[Sentence]:
        """Get high risk sentences."""
        stmt = select(Sentence).where(Sentence.risk_score >= min_risk_score)
        result = await self._session.execute(stmt)
        return result.scalars().all()  # type: ignore[no-any-return]

    async def search_meilisearch(
        self,
        query: str,
        file_id: str | None = None,
        country: str | None = None,
        speaker_name: str | None = None,
        limit: int = 20,
    ) -> list[Sentence]:
        """Full-text search over sentences using Meilisearch."""
        try:
            from bb_paxdata.infrastructure.search.meilisearch_client import (
                search_sentences,
            )

            filters = []
            if file_id:
                filters.append(f"file_id = '{file_id}'")
            if country:
                filters.append(f"country = '{country}'")
            if speaker_name:
                filters.append(f"speaker_name = '{speaker_name}'")

            filter_str = " AND ".join(filters) if filters else None

            result = await search_sentences(
                query=query,
                filters=filter_str,
                limit=limit,
            )

            hits = result.get("hits", [])
            sent_ids = [hit["sent_id"] for hit in hits]

            # Fetch full Sentence objects from database
            stmt = select(Sentence).where(Sentence.sent_id.in_(sent_ids))
            db_result = await self._session.execute(stmt)
            sentences = db_result.scalars().all()

            # Return in the same order as Meilisearch results
            sent_dict = {s.sent_id: s for s in sentences}
            return [sent_dict[sid] for sid in sent_ids if sid in sent_dict]

        except Exception as e:
            logger.warning(
                "meilisearch_search_failed",
                query=query[:100],
                error=str(e),
            )
            # Fallback to SQL LIKE search
            stmt = select(Sentence).where(Sentence.text.ilike(f"%{query}%"))
            if file_id:
                stmt = stmt.where(Sentence.file_id == file_id)
            if country:
                stmt = stmt.where(Sentence.country == country)
            if speaker_name:
                stmt = stmt.where(Sentence.speaker_name == speaker_name)
            stmt = stmt.limit(limit)

            result = await self._session.execute(stmt)
            return result.scalars().all()  # type: ignore[no-any-return]

    async def index_to_meilisearch(self, sentences: list[Sentence]) -> None:
        """Index sentences to Meilisearch for full-text search."""
        try:
            from bb_paxdata.infrastructure.search.meilisearch_client import (
                index_sentences,
            )

            documents = []
            for sent in sentences:
                documents.append(
                    {
                        "sent_id": sent.sent_id,
                        "file_id": sent.file_id,
                        "seg_id": sent.seg_id,
                        "text": sent.text,
                        "speaker_name": sent.speaker_name,
                        "country": sent.country,
                        "dominant_topic": sent.dominant_topic,
                        "emotion_category": sent.emotion_category,
                        "risk_score": sent.risk_score,
                        "vader_compound": sent.vader_compound,
                    }
                )

            await index_sentences(documents)
            logger.info(
                "sentences_indexed_to_meilisearch",
                count=len(sentences),
            )
        except Exception as e:
            logger.warning(
                "sentences_index_to_to_meilisearch_failed",
                error=str(e),
            )

    async def search_by_vector(
        self,
        query_vector: list[float],
        file_id: str | None = None,
        country: str | None = None,
        speaker_name: str | None = None,
        limit: int = 20,
        embedding_dim: int = 384,
    ) -> list[tuple[Sentence, float]]:
        """
        Vector similarity search using pgvector.

        Args:
            query_vector: Query embedding vector (384 dimensions)
            file_id: Optional file filter
            country: Optional country filter
            speaker_name: Optional speaker filter
            limit: Maximum number of results
            embedding_dim: Embedding dimension (default 384)

        Returns:
            List of (Sentence, similarity_score) tuples
        """
        from sqlalchemy import text

        # Determine dialect
        is_postgresql = True
        try:
            dialect_name = self._session.bind.dialect.name
            is_postgresql = dialect_name == "postgresql"
        except Exception:
            is_postgresql = False

        if is_postgresql:
            # Use pgvector for PostgreSQL
            filters = ["embedding IS NOT NULL"]
            params: dict[str, object] = {
                "query_vec": str(query_vector),
                "dim": embedding_dim,
                "limit": limit,
            }

            if file_id:
                filters.append("file_id = :file_id")
                params["file_id"] = file_id

            if country:
                filters.append("country = :country")
                params["country"] = country

            if speaker_name:
                filters.append("speaker_name = :speaker_name")
                params["speaker_name"] = speaker_name

            where_clause = " AND ".join(filters)

            sql = text(
                f"""
                SELECT
                    *,
                    1 - (embedding <=> CAST(:query_vec AS vector(:dim))) AS similarity
                FROM sentences
                WHERE {where_clause}
                ORDER BY embedding <=> CAST(:query_vec AS vector(:dim))
                LIMIT :limit
            """
            )

            result = await self._session.execute(sql, params)
            rows = result.mappings().all()

            # Convert to Sentence objects with similarity scores
            results = []
            for row in rows:
                sent = Sentence(
                    sent_id=row["sent_id"],
                    file_id=row["file_id"],
                    seg_id=row["seg_id"],
                    text=row["text"],
                    speaker_name=row["speaker_name"],
                    country=row["country"],
                )
                results.append((sent, float(row["similarity"] or 0.0)))

            return results
        else:
            # SQLite fallback: compute similarity in Python
            import numpy as np

            stmt = select(Sentence).where(Sentence.embedding.isnot(None))
            if file_id:
                stmt = stmt.where(Sentence.file_id == file_id)
            if country:
                stmt = stmt.where(Sentence.country == country)
            if speaker_name:
                stmt = stmt.where(Sentence.speaker_name == speaker_name)

            rows = (await self._session.execute(stmt)).scalars().all()

            if not rows:
                return []

            target_np = np.array(query_vector, dtype=np.float32)
            target_norm = np.linalg.norm(target_np)

            scored_rows = []
            for r in rows:
                emb = r.embedding
                if emb is not None:
                    if isinstance(emb, str):
                        try:
                            import json

                            emb = json.loads(emb)
                        except Exception:
                            continue
                    emb_np = np.array(emb, dtype=np.float32)
                    emb_norm = np.linalg.norm(emb_np)
                    if emb_norm > 0 and target_norm > 0:
                        sim = float(
                            np.dot(emb_np, target_np) / (emb_norm * target_norm)
                        )
                    else:
                        sim = 0.0
                    scored_rows.append((r, sim))

            scored_rows.sort(key=lambda x: x[1], reverse=True)
            return scored_rows[:limit]
