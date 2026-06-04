import asyncio
import logging
from collections import OrderedDict
from typing import Any, Sequence

import numpy as np
from redis.asyncio import Redis
from redis.exceptions import ConnectionError, TimeoutError

from bb_paxdata.domain.ports.embedding_port import EmbeddingService
from bb_paxdata.infrastructure.cache.redis_embedding_schema import (
    EmbeddingCacheKey,
    EmbeddingSerializer,
)

logger = logging.getLogger(__name__)


class InMemoryLRUCache:
    """Thread-safe LRU fallback when Redis is unavailable."""

    def __init__(self, capacity: int = 10000):
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._capacity = capacity
        self._lock = asyncio.Lock()

    async def get(self, keys: list[str]) -> dict[str, np.ndarray]:
        async with self._lock:
            return {k: self._cache[k] for k in keys if k in self._cache}

    async def set(self, items: dict[str, np.ndarray]) -> None:
        async with self._lock:
            for key, vector in items.items():
                if key in self._cache:
                    self._cache.move_to_end(key)
                else:
                    if len(self._cache) >= self._capacity:
                        self._cache.popitem(last=False)
                    self._cache[key] = vector


class SBERTEmbeddingService(EmbeddingService):
    """
    Unified SBERT embedding service with Redis + In-Memory LRU fallback.
    Singleton pattern via ServiceContainer.
    """

    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    DEFAULT_DIM = 384
    REDIS_TTL_SECONDS = 7 * 24 * 3600  # 7 days
    BATCH_REDIS_SIZE = 100  # mget batch size

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        redis_client: Redis | None = None,
        fallback_cache_size: int = 10000,
    ):
        self.model_name = model_name
        self._redis = redis_client
        self._fallback = InMemoryLRUCache(fallback_cache_size)
        self._model: Any | None = None
        self._dim: int | None = None
        self._lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task[Any]] = set()

    # ── Public API ──
    async def get_embeddings(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.get_model_dimension()), dtype=np.float32)

        # Deduplicate while preserving order info
        unique_texts = list(dict.fromkeys(texts))  # Ordered dedup

        # Phase 1: Cache lookup
        cached, missing = await self._batch_cache_lookup(unique_texts)

        # Phase 2: Compute missing
        computed = {}
        if missing:
            vectors = await self._compute_embeddings(missing)
            computed = dict(zip(missing, vectors))
            # Cache write (async fire-and-forget, errors logged)
            task = asyncio.create_task(self._batch_cache_store(computed))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        # Phase 3: Reconstruct
        all_embeddings = {}
        all_embeddings.update(cached)
        all_embeddings.update(computed)

        # Preserve original order
        result = np.array([all_embeddings[t] for t in texts], dtype=np.float32)
        return result

    async def warm_cache(self, texts: Sequence[str]) -> int:
        """Pre-compute for known corpus. Returns new cached count."""
        _, missing = await self._batch_cache_lookup(list(set(texts)))
        if missing:
            vectors = await self._compute_embeddings(missing)
            await self._batch_cache_store(dict(zip(missing, vectors)))
        return len(missing)

    def get_model_dimension(self) -> int:
        if self._dim is None:
            # Lazy load model to get dimension
            model = self._get_model_sync()
            self._dim = model.get_sentence_embedding_dimension() or self.DEFAULT_DIM
        return self._dim

    # ── Internal: Model Loading ──
    def _get_model_sync(self) -> Any:
        """Synchronous model loading (thread-safe)."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading SBERT model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
        return self._model

    async def _compute_embeddings(self, texts: list[str]) -> np.ndarray:
        """CPU-bound encoding in thread pool."""
        model = self._get_model_sync()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: model.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=False,
            ),
        )

    # ── Internal: Cache Operations ──
    async def _batch_cache_lookup(
        self, texts: list[str]
    ) -> tuple[dict[str, np.ndarray], list[str]]:
        """Batch Redis lookup with fallback to LRU."""
        keys = [self._make_key(t) for t in texts]
        key_to_text = {k: t for k, t in zip(keys, texts)}

        cached: dict[str, np.ndarray] = {}
        missing: list[str] = []

        # Try Redis first
        if self._redis:
            try:
                # Batch mget (chunked for safety)
                for i in range(0, len(keys), self.BATCH_REDIS_SIZE):
                    chunk = keys[i : i + self.BATCH_REDIS_SIZE]
                    values = await self._redis.mget(chunk)

                    for key, val in zip(chunk, values):
                        if val:
                            try:
                                vec = EmbeddingSerializer.deserialize(val)
                                cached[key_to_text[key]] = vec
                            except Exception as e:
                                logger.warning(
                                    f"Cache deserialization failed for {key}: {e}"
                                )
                                missing.append(key_to_text[key])
                        else:
                            missing.append(key_to_text[key])
            except (ConnectionError, TimeoutError, Exception) as e:
                logger.warning(f"Redis unavailable, falling back to LRU: {e}")
                # Fallback to in-memory
                lru_hits = await self._fallback.get(keys)
                for key, vec in lru_hits.items():
                    cached[key_to_text[key]] = vec
                missing = [t for t in texts if t not in cached]
        else:
            # No Redis configured, use LRU only
            lru_hits = await self._fallback.get(keys)
            for key, vec in lru_hits.items():
                cached[key_to_text[key]] = vec
            missing = [t for t in texts if t not in cached]

        return cached, missing

    async def _batch_cache_store(self, items: dict[str, np.ndarray]) -> None:
        """Batch Redis write with fallback to LRU."""
        if not items:
            return

        # Update LRU with Redis keys always
        lru_items = {self._make_key(text): vec for text, vec in items.items()}
        await self._fallback.set(lru_items)

        # Update Redis if available
        if self._redis:
            try:
                async with self._redis.pipeline(transaction=False) as pipe:
                    for text, vec in items.items():
                        key = self._make_key(text)
                        data = EmbeddingSerializer.serialize(vec)
                        pipe.set(key, data, ex=self.REDIS_TTL_SECONDS)
                    await pipe.execute()
                logger.debug(f"Cached {len(items)} embeddings to Redis")
            except (ConnectionError, TimeoutError, Exception) as e:
                logger.warning(f"Redis write failed, keeping LRU only: {e}")

    def _make_key(self, text: str) -> str:
        return EmbeddingCacheKey(
            model_name=self.model_name.replace("/", "_"),
            text_hash=EmbeddingSerializer.hash_text(text),
        ).redis_key()
