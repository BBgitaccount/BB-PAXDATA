"""
CacheCoordinator — Merkezi cache invalidation mekanizması.

Redis ve Disk cache arasındaki tutarsızlığı çözmek için koordinatör.
Redis pub/sub kullanarak dağıtık invalidation sağlar.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from .base import CacheBackend

logger = structlog.get_logger(__name__)

REDIS_AVAILABLE = False
try:
    import redis.asyncio as _redis_check  # noqa: F401

    REDIS_AVAILABLE = True
except ImportError:
    pass


class CacheCoordinator:
    """
    Merkezi cache koordinatörü.

    - Birden fazla cache backend'ini yönetir
    - Delete/clear işlemlerini tüm backend'lere yayarak tutarlılık sağlar
    - Redis pub/sub kullanarak dağıtık invalidation sağlar
    """

    def __init__(
        self,
        primary_backend: CacheBackend,
        secondary_backends: list[CacheBackend] | None = None,
        redis_url: str | None = None,
        enable_pubsub: bool = True,
        pubsub_channel: str = "bbpax:cache_invalidation",
    ) -> None:
        """
        Args:
            primary_backend: Ana cache backend (okuma/yazma için)
            secondary_backends: İkincil backend'ler (invalidation için)
            redis_url: Redis URL for pub/sub (None ise primary_backend'den alır)
            enable_pubsub: Redis pub/sub aktif mi
            pubsub_channel: Pub/sub channel adı
        """
        self._primary = primary_backend
        self._secondaries = secondary_backends or []
        self._enable_pubsub = enable_pubsub
        self._pubsub_channel = pubsub_channel
        self._redis_url = redis_url
        self._redis_client: Any = None
        self._pubsub_task: asyncio.Task | None = None
        self._pubsub_listener_running = False

        # Redis client'ı başlat
        if enable_pubsub and REDIS_AVAILABLE:
            self._init_redis_client()

    def _init_redis_client(self) -> None:
        """Redis client'ı başlat."""
        try:
            import redis.asyncio as aioredis

            url = self._redis_url
            # Eğer RedisCacheBackend ise URL'sinden al
            if url is None and hasattr(self._primary, "_url"):
                url = self._primary._url

            if url:
                self._redis_client = aioredis.Redis.from_url(
                    url, encoding="utf-8", decode_responses=True
                )
                logger.info("cache_coordinator.redis_init", url=url)
        except Exception as exc:
            logger.warning("cache_coordinator.redis_init_failed", error=str(exc))
            self._enable_pubsub = False

    async def start_pubsub_listener(self) -> None:
        """Redis pub/sub listener'ını başlat."""
        if not self._enable_pubsub or not self._redis_client:
            return

        if self._pubsub_listener_running:
            return

        self._pubsub_listener_running = True
        self._pubsub_task = asyncio.create_task(self._pubsub_listener_loop())
        logger.info("cache_coordinator.pubsub_listener_started")

    async def stop_pubsub_listener(self) -> None:
        """Redis pub/sub listener'ını durdur."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None
            self._pubsub_listener_running = False
            logger.info("cache_coordinator.pubsub_listener_stopped")

    async def _pubsub_listener_loop(self) -> None:
        """Pub/sub mesajlarını dinle."""
        if not self._redis_client:
            return

        try:
            pubsub = self._redis_client.pubsub()
            await pubsub.subscribe(self._pubsub_channel)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await self._handle_invalidation_event(data)
                    except Exception as exc:
                        logger.warning(
                            "cache_coordinator.pubsub_message_failed",
                            error=str(exc),
                        )
        except asyncio.CancelledError:
            if self._redis_client:
                await self._redis_client.close()
            raise
        except Exception as exc:
            logger.warning("cache_coordinator.pubsub_listener_failed", error=str(exc))
            self._pubsub_listener_running = False

    async def _handle_invalidation_event(self, data: dict[str, Any]) -> None:
        """Invalidation event'ini işle."""
        event_type = data.get("event")
        key = data.get("key")
        prefix = data.get("prefix")

        if event_type == "delete" and key:
            await self._primary.delete(key)
            for backend in self._secondaries:
                try:
                    await backend.delete(key)
                except Exception as exc:
                    logger.warning(
                        "cache_coordinator.secondary_delete_failed",
                        key=key,
                        backend=type(backend).__name__,
                        error=str(exc),
                    )
        elif event_type == "clear" and prefix is not None:
            await self._primary.clear(prefix)
            for backend in self._secondaries:
                try:
                    await backend.clear(prefix)
                except Exception as exc:
                    logger.warning(
                        "cache_coordinator.secondary_clear_failed",
                        prefix=prefix,
                        backend=type(backend).__name__,
                        error=str(exc),
                    )

    async def _publish_invalidation(
        self, event: str, key: str | None = None, prefix: str | None = None
    ) -> None:
        """Invalidation event'ini yayınla."""
        if not self._enable_pubsub or not self._redis_client:
            return

        try:
            data = {"event": event, "key": key, "prefix": prefix}
            await self._redis_client.publish(self._pubsub_channel, json.dumps(data))
        except Exception as exc:
            logger.warning("cache_coordinator.publish_failed", error=str(exc))

    async def get(self, key: str) -> Any | None:
        """Cache'ten değer al (primary backend)."""
        return await self._primary.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Cache'e değer yaz (primary backend + secondaries)."""
        # Primary backend'e yaz
        await self._primary.set(key, value, ttl)

        # Secondary backend'lere de yaz (tutarlılık için)
        for backend in self._secondaries:
            try:
                await backend.set(key, value, ttl)
            except Exception as exc:
                logger.warning(
                    "cache_coordinator.secondary_set_failed",
                    key=key,
                    backend=type(backend).__name__,
                    error=str(exc),
                )

    async def delete(self, key: str) -> None:
        """
        Cache'ten değer sil (tüm backend'ler + pub/sub).

        Bu işlem tüm backend'lerde ve tüm instance'larda invalidation tetikler.
        """
        # Primary backend'den sil
        await self._primary.delete(key)

        # Secondary backend'lerden sil
        for backend in self._secondaries:
            try:
                await backend.delete(key)
            except Exception as exc:
                logger.warning(
                    "cache_coordinator.secondary_delete_failed",
                    key=key,
                    backend=type(backend).__name__,
                    error=str(exc),
                )

        # Pub/sub ile yayınla
        await self._publish_invalidation("delete", key=key)

    async def exists(self, key: str) -> bool:
        """Cache'te key var mı (primary backend)."""
        return await self._primary.exists(key)

    async def clear(self, prefix: str | None = None) -> int:
        """
        Cache'i temizle (tüm backend'ler + pub/sub).

        Args:
            prefix: Sadece bu prefix ile başlayan key'leri sil

        Returns:
            Silinen key sayısı (primary backend'den)
        """
        # Primary backend'i temizle
        deleted = await self._primary.clear(prefix)

        # Secondary backend'leri temizle
        for backend in self._secondaries:
            try:
                await backend.clear(prefix)
            except Exception as exc:
                logger.warning(
                    "cache_coordinator.secondary_clear_failed",
                    prefix=prefix,
                    backend=type(backend).__name__,
                    error=str(exc),
                )

        # Pub/sub ile yayınla
        await self._publish_invalidation("clear", prefix=prefix)

        return deleted

    async def stats(self) -> dict[str, Any]:
        """Cache istatistikleri (primary backend)."""
        return await self._primary.stats()

    def make_key(self, *parts: str) -> str:
        """Cache anahtarı üret (primary backend)."""
        return self._primary.make_key(*parts)

    async def close(self) -> None:
        """Kaynakları temizle."""
        await self.stop_pubsub_listener()
        if self._redis_client:
            await self._redis_client.close()
