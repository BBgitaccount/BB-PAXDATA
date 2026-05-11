from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from .base import CacheBackend

if TYPE_CHECKING:
    # Bu blok sadece mypy için çalışır, runtime'da import edilmez
    pass

logger = structlog.get_logger(__name__)

REDIS_AVAILABLE = False
try:
    import redis.asyncio as _redis_check  # noqa: F401

    REDIS_AVAILABLE = True
except ImportError:
    pass


class RedisCacheBackend(CacheBackend):
    """
    Redis tabanlı cache backend.
    Kullanmak için: poetry add "redis[asyncio]"
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        key_prefix: str = "bbpax:",
        default_ttl: int = 3600,
    ) -> None:
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis paketi kurulu değil. " "Kurmak için: poetry add 'redis[asyncio]'"
            )
        self._url = url
        self._key_prefix = key_prefix
        self._default_ttl = default_ttl
        self._client: Any = None  # Redis[bytes] yerine Any

    async def _get_client(self) -> Any:
        """Redis client'ı lazy olarak başlat."""
        if self._client is None:
            import redis.asyncio as aioredis  # runtime import — fonksiyon içinde

            self._client = aioredis.Redis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def get(self, key: str) -> Any | None:
        try:
            client = await self._get_client()
            value = await client.get(self._key_prefix + key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as exc:
            logger.warning("redis.get.failed", key=key, error=str(exc))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        try:
            client = await self._get_client()
            serialized = json.dumps(value)
            expire = ttl if ttl is not None else self._default_ttl
            await client.set(self._key_prefix + key, serialized, ex=expire)
        except Exception as exc:
            logger.warning("redis.set.failed", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        try:
            client = await self._get_client()
            await client.delete(self._key_prefix + key)
        except Exception as exc:
            logger.warning("redis.delete.failed", key=key, error=str(exc))

    async def exists(self, key: str) -> bool:
        try:
            client = await self._get_client()
            result = await client.exists(self._key_prefix + key)
            return bool(result)
        except Exception:
            return False

    async def clear(self, prefix: str | None = None) -> int:
        """SCAN kullan, KEYS kullanma — production'da KEYS bloke eder."""
        try:
            client = await self._get_client()
            pattern = self._key_prefix + (prefix or "") + "*"
            deleted = 0
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)
                deleted += 1
            return deleted
        except Exception as exc:
            logger.warning("redis.clear.failed", error=str(exc))
            return 0

    async def stats(self) -> dict[str, Any]:
        try:
            client = await self._get_client()
            info = await client.info()
            size = await client.dbsize()
            return {
                "backend": "redis",
                "total_keys": size,
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as exc:
            return {"backend": "redis", "error": str(exc)}

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            await client.ping()
            return True
        except Exception:
            return False
