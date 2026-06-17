from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, PrivateAttr


class AggregateRoot(BaseModel):
    """Base class for Domain Aggregate Roots to support event collection."""

    _domain_events: list[dict[str, Any]] = PrivateAttr(default_factory=list)

    def record_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
        correlation_id: str | None = None,
        aggregate_id: str | None = None,
        event_version: int | None = None,
    ) -> None:
        """Record a domain event on this aggregate root."""
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            object.__setattr__(self, "_domain_events", [])

        agg_id = aggregate_id
        if agg_id is None:
            agg_id = getattr(self, "id", "unknown")
            if isinstance(agg_id, UUID):
                agg_id = str(agg_id)

        corr_id = correlation_id
        if corr_id is None:
            from bb_paxdata.application.domain.utils.context import get_correlation_id

            corr_id = get_correlation_id()

        from bb_paxdata.infrastructure.events.upcaster import global_upcaster_registry

        evt_version = event_version or global_upcaster_registry.get_latest_version(
            event_type
        )

        self._domain_events.append(
            {
                "aggregate_type": self.__class__.__name__,
                "aggregate_id": str(agg_id),
                "event_type": event_type,
                "event_version": evt_version,
                "payload": payload,
                "actor_id": actor_id,
                "correlation_id": corr_id,
            }
        )

    def clear_events(self) -> None:
        """Clear all domain events on this aggregate root."""
        if hasattr(self, "_domain_events") and self._domain_events:
            self._domain_events.clear()

    def get_events(self) -> list[dict[str, Any]]:
        """Get all domain events on this aggregate root."""
        return getattr(self, "_domain_events", None) or []
