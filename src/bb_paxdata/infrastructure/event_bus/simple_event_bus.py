# src/bb_paxdata/infrastructure/event_bus/simple_event_bus.py
from __future__ import annotations

import logging
from typing import Any

from bb_paxdata.application.domain.ports.event_bus import EventBusPort

logger = logging.getLogger(__name__)


class SimpleEventBus(EventBusPort):
    """Lightweight in-process event bus that logs events.

    Implements EventBusPort protocol. Used by ServiceContainer as the
    default event bus when no Redis/async publisher is required.
    """

    async def publish(
        self, channel: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        """Log the event; production deployments can swap this for Redis."""
        logger.info("Event published: %s/%s - %s", channel, event_type, payload)
