# src/bb_paxdata/application/services/dynamic_few_shot_optimizer.py
from __future__ import annotations

import hashlib
from typing import Any, Callable, Sequence, cast

import numpy as np
import structlog
from bb_paxdata.domain.services.protocols.few_shot_protocols import (
    EmbeddingCacheProtocol,
    ExampleStoreProtocol,
    HumanReviewExample,
    SimilaritySelectorProtocol,
)
from bb_paxdata.infrastructure.nlp.sbert_embedding_service import SBERTEmbeddingService
from redis.asyncio import Redis
from sqlalchemy import select

logger = structlog.get_logger()


class RedisEmbeddingCache(EmbeddingCacheProtocol):
    def __init__(self, redis: Redis | None, prefix: str = "emb:") -> None:
        self._redis = redis
        self._prefix = prefix
        self._fallback: dict[str, list[float]] = {}

    def _key(self, text_hash: str) -> str:
        return f"{self._prefix}{text_hash}"

    async def get(self, text_hash: str) -> list[float] | None:
        if self._redis:
            try:
                raw = await self._redis.get(self._key(text_hash))
                if raw is not None:
                    import json

                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    return cast(list[float], json.loads(raw))
            except Exception as e:
                logger.warning(
                    f"Redis get failed in Embedding Cache, falling back: {e}"
                )
        return self._fallback.get(text_hash)

    async def set(
        self, text_hash: str, vector: list[float], ttl_sec: int = 86400
    ) -> None:
        self._fallback[text_hash] = vector
        if self._redis:
            try:
                import json

                await self._redis.setex(
                    self._key(text_hash), ttl_sec, json.dumps(vector)
                )
            except Exception as e:
                logger.warning(f"Redis set failed in Embedding Cache: {e}")


class DbExampleStore(ExampleStoreProtocol):
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    async def get_all_gold_standards(self) -> Sequence[HumanReviewExample]:
        from bb_paxdata.infrastructure.db.human_review_table import HumanReviewORM
        from bb_paxdata.infrastructure.db.models import AISentenceAnalysis, Sentence

        stmt = (
            select(HumanReviewORM, Sentence)
            .join(
                AISentenceAnalysis,
                HumanReviewORM.analysis_id == AISentenceAnalysis.sent_id,
            )
            .join(Sentence, AISentenceAnalysis.sent_id == Sentence.sent_id)
            .where(HumanReviewORM.human_dominant_frame.isnot(None))
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()

            examples = []
            for orm, sent in rows:
                examples.append(
                    HumanReviewExample(
                        review_id=orm.id,
                        sentence_text=sent.text,
                        sentence_embedding=sent.embedding,
                        assigned_sentiment=str(orm.human_sentiment_score or "neutral"),
                        assigned_risk_score=float(orm.human_sbi_score or 0.0),
                        assigned_frame=orm.human_dominant_frame,
                        speaker_name=sent.speaker_name,
                        country=sent.country or "",
                        panel_id=sent.file_id,
                    )
                )
            return examples

    async def get_by_panel(self, panel_id: str) -> Sequence[HumanReviewExample]:
        from bb_paxdata.infrastructure.db.human_review_table import HumanReviewORM
        from bb_paxdata.infrastructure.db.models import AISentenceAnalysis, Sentence

        stmt = (
            select(HumanReviewORM, Sentence)
            .join(
                AISentenceAnalysis,
                HumanReviewORM.analysis_id == AISentenceAnalysis.sent_id,
            )
            .join(Sentence, AISentenceAnalysis.sent_id == Sentence.sent_id)
            .where(
                HumanReviewORM.human_dominant_frame.isnot(None),
                Sentence.file_id == panel_id,
            )
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()

            examples = []
            for orm, sent in rows:
                examples.append(
                    HumanReviewExample(
                        review_id=orm.id,
                        sentence_text=sent.text,
                        sentence_embedding=sent.embedding,
                        assigned_sentiment=str(orm.human_sentiment_score or "neutral"),
                        assigned_risk_score=float(orm.human_sbi_score or 0.0),
                        assigned_frame=orm.human_dominant_frame,
                        speaker_name=sent.speaker_name,
                        country=sent.country or "",
                        panel_id=sent.file_id,
                    )
                )
            return examples

    async def get_by_country(self, country: str) -> Sequence[HumanReviewExample]:
        from bb_paxdata.infrastructure.db.human_review_table import HumanReviewORM
        from bb_paxdata.infrastructure.db.models import AISentenceAnalysis, Sentence

        stmt = (
            select(HumanReviewORM, Sentence)
            .join(
                AISentenceAnalysis,
                HumanReviewORM.analysis_id == AISentenceAnalysis.sent_id,
            )
            .join(Sentence, AISentenceAnalysis.sent_id == Sentence.sent_id)
            .where(
                HumanReviewORM.human_dominant_frame.isnot(None),
                Sentence.country == country,
            )
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()

            examples = []
            for orm, sent in rows:
                examples.append(
                    HumanReviewExample(
                        review_id=orm.id,
                        sentence_text=sent.text,
                        sentence_embedding=sent.embedding,
                        assigned_sentiment=str(orm.human_sentiment_score or "neutral"),
                        assigned_risk_score=float(orm.human_sbi_score or 0.0),
                        assigned_frame=orm.human_dominant_frame,
                        speaker_name=sent.speaker_name,
                        country=sent.country or "",
                        panel_id=sent.file_id,
                    )
                )
            return examples


class VectorSimilaritySelector(SimilaritySelectorProtocol):
    def __init__(
        self,
        embedding_service: SBERTEmbeddingService,
        example_store: ExampleStoreProtocol,
        cache: EmbeddingCacheProtocol,
        default_min_similarity: float = 0.65,
    ) -> None:
        self._embed = embedding_service
        self._store = example_store
        self._cache = cache
        self._default_min = default_min_similarity

    async def select(
        self, target_text: str, n_examples: int = 3, min_similarity: float | None = None
    ) -> Sequence[HumanReviewExample]:
        threshold = min_similarity if min_similarity is not None else self._default_min

        # 1. Embed target with cache check
        target_hash = hashlib.sha256(target_text.encode()).hexdigest()
        target_vec = await self._cache.get(target_hash)
        if target_vec is None:
            emb = await self._embed.get_embeddings([target_text])
            target_vec = emb[0].tolist()
            await self._cache.set(target_hash, target_vec)

        target_np = np.array(target_vec, dtype=np.float32)

        # 2. Retrieve gold standards
        gold_examples = await self._store.get_all_gold_standards()
        if not gold_examples:
            logger.warning("few_shot_no_gold_data")
            return []

        # 3. Batch embedding with cache hydration
        texts_to_embed: list[str] = []
        indices_to_embed: list[int] = []
        embeddings: list[np.ndarray | None] = [None] * len(gold_examples)

        for idx, ex in enumerate(gold_examples):
            if ex.sentence_embedding is not None:
                embeddings[idx] = np.array(ex.sentence_embedding, dtype=np.float32)
            else:
                h = hashlib.sha256(ex.sentence_text.encode()).hexdigest()
                cached = await self._cache.get(h)
                if cached:
                    embeddings[idx] = np.array(cached, dtype=np.float32)
                else:
                    texts_to_embed.append(ex.sentence_text)
                    indices_to_embed.append(idx)

        if texts_to_embed:
            computed = await self._embed.get_embeddings(texts_to_embed)
            for arr, idx in zip(computed, indices_to_embed):
                vec = arr.tolist()
                embeddings[idx] = np.array(vec, dtype=np.float32)
                h = hashlib.sha256(
                    gold_examples[idx].sentence_text.encode()
                ).hexdigest()
                await self._cache.set(h, vec)

        # 4. Cosine similarity matrix computation
        valid_embeddings = [e for e in embeddings if e is not None]
        if not valid_embeddings:
            return []

        review_matrix = np.stack(valid_embeddings)
        norms_target = float(np.linalg.norm(target_np))
        norms_reviews = np.linalg.norm(review_matrix, axis=1)

        # Avoid division by zero
        norms_reviews[norms_reviews == 0] = 1e-6
        if norms_target == 0:
            norms_target = 1e-6

        similarities = np.dot(review_matrix, target_np) / (norms_reviews * norms_target)

        # 5. Top-K filtering with threshold
        top_indices = np.argsort(similarities)[::-1][:n_examples]
        selected: list[HumanReviewExample] = []
        for idx in top_indices:
            if similarities[idx] >= threshold:
                selected.append(gold_examples[idx])

        logger.info(
            "few_shot_selected",
            target_len=len(target_text),
            candidates=len(gold_examples),
            selected=len(selected),
            top_similarity=(
                float(similarities[top_indices[0]]) if len(top_indices) else None
            ),
        )
        return selected
