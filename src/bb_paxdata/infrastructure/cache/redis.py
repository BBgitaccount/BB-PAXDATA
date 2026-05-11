"""
RedisCacheBackend — Redis tabanlı cache implementasyonu.

Dağıtık / çok worker senaryoları için.
Redis kurulu değilse graceful degrade yapar.
"""

from __future__ import annotations

import json
from typing import Any

try:
    import redis.asyncio as redis  # type: ignore
    from redis.exceptions import ConnectionError, RedisError  # type: ignore

    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    ConnectionError = Exception
    RedisError = Exception
    REDIS_AVAILABLE = False

try:
    import structlog
except ImportError:
    structlog = None

from .base import CacheBackend


class RedisCacheBackend(CacheBackend):
    """
    Redis tabanlı cache.
    Dağıtık / çok worker senaryosu için.

    __init__ parametreleri:
      url: str              (default: "redis://localhost:6379/0")
      key_prefix: str       (default: "bbpax:")
      default_ttl: int      (default: 3600)
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        key_prefix: str = "bbpax:",
        default_ttl: int = 3600,
    ) -> None:
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis[asyncio] is required for RedisCacheBackend. "
                "Install with: pip install 'redis[asyncio]'"
            )

        self.url = url
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self._client: redis.Redis | None = None
        self._connection_failed = False

        if structlog:
            self._logger = structlog.get_logger(__name__)
        else:
            import logging

            self._logger = logging.getLogger(__name__)

    async def _get_client(self) -> redis.Redis | None:
        """Redis client'ını al (lazy connection)."""
        if self._connection_failed:
            return None

        if self._client is None:
            try:
                self._client = redis.from_url(self.url)
                # Bağlantı testi
                await self._client.ping()
                self._connection_failed = False
            except (ConnectionError, RedisError) as exc:
                self._logger.warning("redis.connection.failed", error=str(exc))
                self._connection_failed = True
                self._client = None
                return None

        return self._client

    def _make_redis_key(self, key: str) -> str:
        """Redis key formatı."""
        return f"{self.key_prefix}{key}"

    async def get(self, key: str) -> Any | None:
        """Key'den değeri oku."""
        client = await self._get_client()
        if client is None:
            return None

        try:
            redis_key = self._make_redis_key(key)
            value = await client.get(redis_key)

            if value is None:
                return None

            # JSON deserialize
            return json.loads(value)

        except (ConnectionError, RedisError, json.JSONDecodeError) as exc:
            self._logger.warning("redis.get.failed", key=key, error=str(exc))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Değeri Redis'e yaz."""
        client = await self._get_client()
        if client is None:
            return

        try:
            redis_key = self._make_redis_key(key)
            serialized_value = json.dumps(
                value, ensure_ascii=False, separators=(",", ":")
            )

            # TTL kullan
            expire_time = ttl if ttl is not None else self.default_ttl

            await client.setex(redis_key, expire_time, serialized_value)

        except (ConnectionError, RedisError, TypeError) as exc:
            self._logger.warning("redis.set.failed", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        """Key'i sil."""
        client = await self._get_client()
        if client is None:
            return

        try:
            redis_key = self._make_redis_key(key)
            await client.delete(redis_key)
        except (ConnectionError, RedisError) as exc:
            self._logger.warning("redis.delete.failed", key=key, error=str(exc))

    async def exists(self, key: str) -> bool:
        """Key var mı kontrol et."""
        client = await self._get_client()
        if client is None:
            return False

        try:
            redis_key = self._make_redis_key(key)
            return bool(await client.exists(redis_key))
        except (ConnectionError, RedisError) as exc:
            self._logger.warning("redis.exists.failed", key=key, error=str(exc))
            return False

    async def clear(self, prefix: str | None = None) -> int:
        """Cache'i temizle. Prefix verilirse sadece o prefix ile başlayanları sil."""
        client = await self._get_client()
        if client is None:
            return 0

        deleted_count = 0

        try:
            if prefix:
                # Prefix ile eşleşen key'leri bul ve sil
                search_pattern = f"{self.key_prefix}{prefix}*"
                async for key in client.scan_iter(match=search_pattern):
                    await client.delete(key)
                    deleted_count += 1
            else:
                # Tüm bbpax: prefix'li key'leri sil
                search_pattern = f"{self.key_prefix}*"
                async for key in client.scan_iter(match=search_pattern):
                    await client.delete(key)
                    deleted_count += 1

        except (ConnectionError, RedisError) as exc:
            self._logger.warning("redis.clear.failed", error=str(exc))

        return deleted_count

    async def stats(self) -> dict[str, Any]:
        """Redis istatistikleri."""
        client = await self._get_client()
        if client is None:
            return {
                "connected": False,
                "error": "Redis connection failed",
            }

        try:
            # Redis info
            info = await client.info()

            # Key sayısı (sadece bizim prefix'li olanlar)
            key_count = 0
            async for _ in client.scan_iter(match=f"{self.key_prefix}*"):
                key_count += 1

            return {
                "connected": True,
                "key_count": key_count,
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "url": self.url,
                "key_prefix": self.key_prefix,
            }

        except (ConnectionError, RedisError) as exc:
            self._logger.warning("redis.stats.failed", error=str(exc))
            return {
                "connected": False,
                "error": str(exc),
            }

    async def health(self) -> bool:
        """Redis sağlık kontrolü."""
        client = await self._get_client()
        if client is None:
            return False

        try:
            await client.ping()
            return True
        except (ConnectionError, RedisError):
            return False
