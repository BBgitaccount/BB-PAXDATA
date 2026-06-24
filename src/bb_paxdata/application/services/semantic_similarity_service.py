"""Semantic similarity service for sentence similarity and clustering."""

from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.repositories.sentence import SentenceRepository
from bb_paxdata.infrastructure.nlp.sbert_embedding_service import SBERTEmbeddingService

logger = structlog.get_logger(__name__)


class SemanticSimilarityService:
    """Service for semantic similarity operations."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        embedding_service: SBERTEmbeddingService,
        embedding_dim: int = 384,
    ) -> None:
        """
        Initialize semantic similarity service.

        Args:
            session_factory: Database session factory
            embedding_service: Embedding service
            embedding_dim: Embedding dimension (default 384)
        """
        self._session_factory = session_factory
        self._embed = embedding_service
        self._embedding_dim = embedding_dim

    async def find_similar_sentences(
        self,
        sentence_text: str,
        file_id: str | None = None,
        country: str | None = None,
        speaker_name: str | None = None,
        min_similarity: float = 0.7,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Find sentences similar to the given text using pgvector cosine similarity.

        Args:
            sentence_text: Input sentence text
            file_id: Optional file filter
            country: Optional country filter
            speaker_name: Optional speaker filter
            min_similarity: Minimum similarity threshold (0-1)
            limit: Maximum number of results

        Returns:
            List of similar sentences with similarity scores
        """
        # Get embedding for input sentence
        vector_arr = (await self._embed.get_embeddings([sentence_text]))[0]
        query_vector = vector_arr.tolist()

        async with self._session_factory() as session:
            repo = SentenceRepository(session=session)
            results = await repo.search_by_vector(
                query_vector=query_vector,
                file_id=file_id,
                country=country,
                speaker_name=speaker_name,
                limit=limit * 2,  # Get more to filter by threshold
                embedding_dim=self._embedding_dim,
            )

        # Filter by threshold and convert to dict
        filtered_results = [
            {
                "sent_id": sent.sent_id,
                "text": sent.text,
                "speaker_name": sent.speaker_name or "",
                "country": sent.country or "",
                "file_id": sent.file_id,
                "dominant_topic": sent.dominant_topic or "",
                "risk_score": sent.risk_score or 0,
                "emotion_category": sent.emotion_category or "",
                "similarity_score": score,
            }
            for sent, score in results
            if score >= min_similarity
        ]

        # Sort by similarity and limit
        filtered_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return filtered_results[:limit]

    async def get_sentence_embeddings_for_clustering(
        self,
        file_id: str | None = None,
        country: str | None = None,
        dominant_topic: str | None = None,
        limit: int = 1000,
    ) -> tuple[list[str], list[list[float]], list[dict[str, Any]]]:
        """
        Get sentence embeddings for clustering.

        Args:
            file_id: Optional file filter
            country: Optional country filter
            dominant_topic: Optional topic filter
            limit: Maximum number of sentences

        Returns:
            Tuple of (sentence_ids, embeddings, metadata)
        """
        from bb_paxdata.infrastructure.db.models import Sentence

        async with self._session_factory() as session:
            stmt = select(Sentence).where(Sentence.embedding.isnot(None))

            if file_id:
                stmt = stmt.where(Sentence.file_id == file_id)
            if country:
                stmt = stmt.where(Sentence.country == country)
            if dominant_topic:
                stmt = stmt.where(Sentence.dominant_topic == dominant_topic)

            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            sentences = result.scalars().all()

        sentence_ids = []
        embeddings = []
        metadata = []

        for sent in sentences:
            emb = sent.embedding
            if emb is None:
                continue

            if isinstance(emb, str):
                import json

                try:
                    emb = json.loads(emb)
                except Exception:
                    continue

            if not isinstance(emb, list) or len(emb) != self._embedding_dim:
                continue

            sentence_ids.append(sent.sent_id)
            embeddings.append(emb)
            metadata.append(
                {
                    "sent_id": sent.sent_id,
                    "text": sent.text,
                    "speaker_name": sent.speaker_name or "",
                    "country": sent.country or "",
                    "file_id": sent.file_id,
                    "dominant_topic": sent.dominant_topic or "",
                    "risk_score": sent.risk_score or 0,
                    "emotion_category": sent.emotion_category or "",
                }
            )

        logger.info(
            "embeddings_extracted_for_clustering",
            count=len(embeddings),
            filters={"file_id": file_id, "country": country, "topic": dominant_topic},
        )

        return sentence_ids, embeddings, metadata

    async def get_topic_summary(
        self,
        topic: str,
        file_id: str | None = None,
        country: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get topic-based summary with speaker positions and evolution over time.

        Args:
            topic: Topic to summarize
            file_id: Optional file filter
            country: Optional country filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with topic summary, speaker positions, and temporal evolution
        """
        from bb_paxdata.infrastructure.db.models import Sentence

        async with self._session_factory() as session:
            stmt = select(Sentence).where(Sentence.dominant_topic == topic)

            if file_id:
                stmt = stmt.where(Sentence.file_id == file_id)
            if country:
                stmt = stmt.where(Sentence.country == country)

            stmt = stmt.order_by(Sentence.global_sent_order)
            result = await session.execute(stmt)
            sentences = result.scalars().all()

        # Group by speaker
        speaker_positions: dict[str, list[dict[str, Any]]] = {}
        for sent in sentences:
            speaker = sent.speaker_name or "Unknown"
            if speaker not in speaker_positions:
                speaker_positions[speaker] = []

            speaker_positions[speaker].append(
                {
                    "sent_id": sent.sent_id,
                    "text": sent.text,
                    "sentiment": sent.vader_compound or 0,
                    "risk_score": sent.risk_score or 0,
                    "emotion_category": sent.emotion_category or "",
                    "global_order": sent.global_sent_order or 0,
                }
            )

        # Calculate speaker statistics
        speaker_stats = {}
        for speaker, utterances in speaker_positions.items():
            avg_sentiment = sum(u["sentiment"] for u in utterances) / len(utterances)
            avg_risk = sum(u["risk_score"] for u in utterances) / len(utterances)
            emotion_dist: dict[str, int] = {}
            for u in utterances:
                emotion = u["emotion_category"]
                emotion_dist[emotion] = emotion_dist.get(emotion, 0) + 1

            speaker_stats[speaker] = {
                "utterance_count": len(utterances),
                "avg_sentiment": avg_sentiment,
                "avg_risk": avg_risk,
                "emotion_distribution": emotion_dist,
            }

        # Temporal evolution (by global order)
        temporal_segments = []
        if sentences:
            total_sentences = len(sentences)
            segment_size = max(10, total_sentences // 5)  # 5 segments
            for i in range(0, total_sentences, segment_size):
                segment = sentences[i : i + segment_size]
                if not segment:
                    continue

                avg_sentiment = sum(s.vader_compound or 0 for s in segment) / len(
                    segment
                )
                avg_risk = sum(s.risk_score or 0 for s in segment) / len(segment)

                speakers_in_segment = set(
                    s.speaker_name for s in segment if s.speaker_name
                )

                temporal_segments.append(
                    {
                        "start_order": segment[0].global_sent_order or 0,
                        "end_order": segment[-1].global_sent_order or 0,
                        "sentence_count": len(segment),
                        "avg_sentiment": avg_sentiment,
                        "avg_risk": avg_risk,
                        "speakers": list(speakers_in_segment),
                    }
                )

        return {
            "topic": topic,
            "total_sentences": len(sentences),
            "speaker_positions": speaker_positions,
            "speaker_statistics": speaker_stats,
            "temporal_evolution": temporal_segments,
        }
