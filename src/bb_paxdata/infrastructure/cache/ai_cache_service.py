from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.db.repositories.analysis import AnalysisRepository

logger = structlog.get_logger()


class AICacheService:
    """
    Redis-backed cache service for AI responses.
    Uses Redis as L1 cache and database as L2 cache (write-through).
    """

    def __init__(
        self,
        redis_backend: RedisCacheBackend,
        analysis_repository: AnalysisRepository | None = None,
        redis_ttl: int = 3600,  # 1 hour default TTL
        enable_redis: bool = True,
    ) -> None:
        self._redis = redis_backend
        self._db_repo = analysis_repository
        self._redis_ttl = redis_ttl
        self._enable_redis = enable_redis

    def _make_redis_key(self, cache_hash: str, file_id: str | None = None) -> str:
        """Generate Redis key for cache entry."""
        if file_id:
            return f"ai_cache:{cache_hash}:{file_id}"
        return f"ai_cache:{cache_hash}"

    async def get(
        self, cache_hash: str, file_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get cached AI response from Redis (L1) or database (L2).

        Args:
            cache_hash: Hash of the cache key
            file_id: Optional file ID for scoped caching

        Returns:
            Cached result as dict or None if not found
        """
        redis_key = self._make_redis_key(cache_hash, file_id)

        # Try Redis first (L1 cache)
        if self._enable_redis:
            try:
                cached = await self._redis.get(redis_key)
                if cached:
                    logger.info(
                        "ai_cache_redis_hit",
                        cache_hash=cache_hash[:16],
                        file_id=file_id,
                    )
                    return cached
            except Exception as e:
                logger.warning(
                    "ai_cache_redis_get_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

        # Fallback to database (L2 cache)
        if self._db_repo:
            try:
                db_result = await self._db_repo.get_cache(cache_hash, file_id)
                if db_result:
                    # Populate Redis for future requests (write-back)
                    if self._enable_redis:
                        try:
                            await self._redis.set(
                                redis_key,
                                {"result_json": db_result.result_json},
                                ttl=self._redis_ttl,
                            )
                        except Exception as e:
                            logger.warning(
                                "ai_cache_redis_writeback_failed",
                                cache_hash=cache_hash[:16],
                                error=str(e),
                            )
                    logger.info(
                        "ai_cache_db_hit",
                        cache_hash=cache_hash[:16],
                        file_id=file_id,
                    )
                    return {"result_json": db_result.result_json}
            except Exception as e:
                logger.warning(
                    "ai_cache_db_get_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

        return None

    async def set(
        self,
        cache_hash: str,
        result_json: str,
        model_used: str,
        backend_used: str,
        file_id: str | None = None,
    ) -> None:
        """
        Set cached AI response in both Redis (L1) and database (L2).

        Args:
            cache_hash: Hash of the cache key
            result_json: JSON string of the result
            model_used: AI model used
            backend_used: Backend used
            file_id: Optional file ID for scoped caching
        """
        redis_key = self._make_redis_key(cache_hash, file_id)
        cache_data = {
            "result_json": result_json,
            "model_used": model_used,
            "backend_used": backend_used,
        }

        # Write to Redis (L1 cache)
        if self._enable_redis:
            try:
                await self._redis.set(redis_key, cache_data, ttl=self._redis_ttl)
                logger.info(
                    "ai_cache_redis_set",
                    cache_hash=cache_hash[:16],
                    file_id=file_id,
                )
            except Exception as e:
                logger.warning(
                    "ai_cache_redis_set_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

        # Write to database (L2 cache - persistent)
        if self._db_repo:
            try:
                await self._db_repo.set_cache(
                    cache_hash, result_json, model_used, backend_used, file_id
                )
                logger.info(
                    "ai_cache_db_set",
                    cache_hash=cache_hash[:16],
                    file_id=file_id,
                )
            except Exception as e:
                logger.warning(
                    "ai_cache_db_set_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

    async def delete(self, cache_hash: str, file_id: str | None = None) -> None:
        """
        Delete cached AI response from both Redis and database.

        Args:
            cache_hash: Hash of the cache key
            file_id: Optional file ID for scoped caching
        """
        redis_key = self._make_redis_key(cache_hash, file_id)

        # Delete from Redis
        if self._enable_redis:
            try:
                await self._redis.delete(redis_key)
                logger.info(
                    "ai_cache_redis_delete",
                    cache_hash=cache_hash[:16],
                    file_id=file_id,
                )
            except Exception as e:
                logger.warning(
                    "ai_cache_redis_delete_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

        # Delete from database (would need to implement this in AnalysisRepository)
        # For now, we only delete from Redis


class AIFailCacheService:
    """
    Redis-backed cache service for AI failure analysis.
    Uses Redis as L1 cache and database as L2 cache (write-through).
    """

    def __init__(
        self,
        redis_backend: RedisCacheBackend,
        analysis_repository: AnalysisRepository | None = None,
        redis_ttl: int = 7200,  # 2 hours default TTL for failures
        enable_redis: bool = True,
    ) -> None:
        self._redis = redis_backend
        self._db_repo = analysis_repository
        self._redis_ttl = redis_ttl
        self._enable_redis = enable_redis

    def _make_redis_key(self, cache_hash: str) -> str:
        """Generate Redis key for fail cache entry."""
        return f"ai_fail_cache:{cache_hash}"

    async def get(self, cache_hash: str) -> dict[str, Any] | None:
        """
        Get cached AI failure analysis from Redis (L1) or database (L2).

        Args:
            cache_hash: Hash of the cache key

        Returns:
            Cached result as dict or None if not found
        """
        redis_key = self._make_redis_key(cache_hash)

        # Try Redis first (L1 cache)
        if self._enable_redis:
            try:
                cached = await self._redis.get(redis_key)
                if cached:
                    logger.info(
                        "ai_fail_cache_redis_hit",
                        cache_hash=cache_hash[:16],
                    )
                    return cached
            except Exception as e:
                logger.warning(
                    "ai_fail_cache_redis_get_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

        # Fallback to database (L2 cache)
        if self._db_repo:
            try:
                db_result = await self._db_repo.get_fail_cache(cache_hash)
                if db_result:
                    # Populate Redis for future requests (write-back)
                    if self._enable_redis:
                        try:
                            await self._redis.set(
                                redis_key,
                                {"result_json": db_result.result_json},
                                ttl=self._redis_ttl,
                            )
                        except Exception as e:
                            logger.warning(
                                "ai_fail_cache_redis_writeback_failed",
                                cache_hash=cache_hash[:16],
                                error=str(e),
                            )
                    logger.info(
                        "ai_fail_cache_db_hit",
                        cache_hash=cache_hash[:16],
                    )
                    return {"result_json": db_result.result_json}
            except Exception as e:
                logger.warning(
                    "ai_fail_cache_db_get_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

        return None

    async def set(
        self,
        cache_hash: str,
        result_json: str,
        model_used: str,
        backend_used: str,
    ) -> None:
        """
        Set cached AI failure analysis in both Redis (L1) and database (L2).

        Args:
            cache_hash: Hash of the cache key
            result_json: JSON string of the result
            model_used: AI model used
            backend_used: Backend used
        """
        redis_key = self._make_redis_key(cache_hash)
        cache_data = {
            "result_json": result_json,
            "model_used": model_used,
            "backend_used": backend_used,
        }

        # Write to Redis (L1 cache)
        if self._enable_redis:
            try:
                await self._redis.set(redis_key, cache_data, ttl=self._redis_ttl)
                logger.info(
                    "ai_fail_cache_redis_set",
                    cache_hash=cache_hash[:16],
                )
            except Exception as e:
                logger.warning(
                    "ai_fail_cache_redis_set_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )

        # Write to database (L2 cache - persistent)
        if self._db_repo:
            try:
                await self._db_repo.set_fail_cache(
                    cache_hash, result_json, model_used, backend_used
                )
                logger.info(
                    "ai_fail_cache_db_set",
                    cache_hash=cache_hash[:16],
                )
            except Exception as e:
                logger.warning(
                    "ai_fail_cache_db_set_failed",
                    cache_hash=cache_hash[:16],
                    error=str(e),
                )
