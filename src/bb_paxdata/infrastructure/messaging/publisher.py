import json
from typing import Any

import structlog

from bb_paxdata.config.settings import get_settings

logger = structlog.get_logger(__name__)


class RedisEventPublisher:
    """Publishes asynchronous events to Redis channels to trigger background tasks."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as aioredis

            self._client = aioredis.Redis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._client

    async def publish_event(self, channel: str, event_type: str, data: dict[str, Any]):
        """Publish a JSON payload to a Redis channel asynchronously."""
        try:
            client = await self._get_client()
            payload = {"event_type": event_type, "data": data}
            await client.publish(channel, json.dumps(payload))
            logger.info(f"Published event '{event_type}' to channel '{channel}'")
        except Exception as e:
            logger.error(f"Failed to publish event '{event_type}' to Redis: {e}")


_publisher: RedisEventPublisher | None = None


def get_publisher() -> RedisEventPublisher:
    """Retrieve the global RedisEventPublisher instance."""
    global _publisher
    if _publisher is None:
        settings = get_settings()
        _publisher = RedisEventPublisher(redis_url=settings.redis_url)
    return _publisher
