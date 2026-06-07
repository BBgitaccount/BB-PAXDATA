# src/bb_paxdata/domain/ports/event_bus.py
from __future__ import annotations

from typing import Any, Protocol


class EventBusPort(Protocol):
    async def publish(
        self, channel: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        """Publish a domain event to a messaging channel."""
        ...
