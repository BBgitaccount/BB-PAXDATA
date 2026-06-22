import asyncio
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from redis.asyncio import Redis

from bb_paxdata.infrastructure.cache.redis_embedding_schema import EmbeddingSerializer
from bb_paxdata.infrastructure.nlp.sbert_embedding_service import SBERTEmbeddingService


@pytest.fixture
def mock_redis():
    redis = AsyncMock(spec=Redis)
    redis.mget = AsyncMock()

    # Configure pipeline mock
    pipe = MagicMock()
    pipe.set = MagicMock()  # regular method, not async!
    pipe.execute = AsyncMock()  # async method!

    pipe_ctx = MagicMock()
    pipe_ctx.__aenter__ = AsyncMock(return_value=pipe)
    pipe_ctx.__aexit__ = AsyncMock()

    redis.pipeline.return_value = pipe_ctx
    return redis


@pytest.mark.asyncio
class TestSBERTEmbeddingService:
    async def test_empty_input(self, mock_redis):
        svc = SBERTEmbeddingService(redis_client=mock_redis)
        result = await svc.get_embeddings([])
        assert result.shape == (0, 384)

    async def test_cache_hit_redis(self, mock_redis):
        """Redis'ten okunan embedding doğru şekilde deserialize edilmeli."""
        text = "Test sentence"
        vector = np.random.randn(384).astype(np.float32)
        serialized = EmbeddingSerializer.serialize(vector)

        mock_redis.mget.return_value = [serialized]

        svc = SBERTEmbeddingService(redis_client=mock_redis)
        result = await svc.get_embeddings([text])

        assert result.shape == (1, 384)
        np.testing.assert_array_almost_equal(result[0], vector)
        mock_redis.mget.assert_called_once()

    async def test_cache_miss_computes_and_stores(self, mock_redis):
        """Cache miss durumunda hesapla ve Redis'e yaz."""
        mock_redis.mget.return_value = [None]

        svc = SBERTEmbeddingService(redis_client=mock_redis)
        # Model'i mockla
        svc._model = MagicMock()
        svc._model.encode.return_value = np.random.randn(1, 384).astype(np.float32)
        svc._dim = 384

        result = await svc.get_embeddings(["New sentence"])
        assert result.shape == (1, 384)

        # Yield to event loop to allow fire-and-forget task to run
        await asyncio.sleep(0.05)
        mock_redis.pipeline.assert_called_once_with(transaction=False)

    async def test_redis_down_fallback_lru(self, mock_redis):
        """Redis çökerse LRU cache devreye girmeli."""
        from redis.exceptions import ConnectionError

        mock_redis.mget.side_effect = ConnectionError("Redis down")

        svc = SBERTEmbeddingService(redis_client=mock_redis)
        svc._model = MagicMock()
        svc._model.encode.return_value = np.random.randn(1, 384).astype(np.float32)
        svc._dim = 384

        # İlk çağrı (cache miss, model çalışır, LRU'ya yazar)
        result1 = await svc.get_embeddings(["Fallback test"])
        assert result1.shape == (1, 384)

        # Yield to event loop so that LRU cache background write completes
        await asyncio.sleep(0.05)

        # İkinci çağrı (LRU'dan gelmeli, model çağrılmamalı)
        svc._model.encode.reset_mock()
        result2 = await svc.get_embeddings(["Fallback test"])
        assert result2.shape == (1, 384)
        svc._model.encode.assert_not_called()

    async def test_deduplication(self, mock_redis):
        """Aynı metinler tek kez encode edilmeli."""
        mock_redis.mget.return_value = [None, None]

        svc = SBERTEmbeddingService(redis_client=mock_redis)
        svc._model = MagicMock()
        svc._model.encode.return_value = np.random.randn(2, 384).astype(np.float32)
        svc._dim = 384

        await svc.get_embeddings(["Dup", "Dup", "Unique"])

        # 3 metin, 2 unique → encode 1 kez çağrılır
        assert svc._model.encode.call_count == 1
        args = svc._model.encode.call_args[0][0]
        assert len(args) == 2  # Deduplicated

    async def test_warm_cache(self, mock_redis):
        """Warm cache pre-computation."""
        mock_redis.mget.return_value = [None]

        svc = SBERTEmbeddingService(redis_client=mock_redis)
        svc._model = MagicMock()
        svc._model.encode.return_value = np.random.randn(1, 384).astype(np.float32)
        svc._dim = 384

        count = await svc.warm_cache(["Pre-warm text"])
        assert count == 1
