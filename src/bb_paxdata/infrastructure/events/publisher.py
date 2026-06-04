"""Append-only domain event publisher."""

from datetime import UTC, datetime
from typing import Any

from bb_paxdata.infrastructure.db.models import DomainEvent
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession


class EventPublisher:
    """Writes immutable domain events to the WORM event store.

    Usage:
        publisher = EventPublisher(db)
        await publisher.emit(
            aggregate_type="AISentenceAnalysis",
            aggregate_id=sent_id,
            event_type="AnalysisCompleted",
            payload={"ai_risk_score": 4, "confidence": 0.85},
            actor_id="system",
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def emit(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Persist an immutable domain event. Never call UPDATE/DELETE after this."""
        event = DomainEvent(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=datetime.now(UTC),
        )
        self.db.add(event)
        # Do NOT flush here — let the caller manage the transaction boundary.

    async def emit_batch(self, events: list[dict[str, Any]]) -> None:
        """Bulk emit multiple events in a single transaction."""
        if not events:
            return
        stmt = insert(DomainEvent).values(
            [
                {
                    "aggregate_type": e["aggregate_type"],
                    "aggregate_id": e["aggregate_id"],
                    "event_type": e["event_type"],
                    "payload": e["payload"],
                    "actor_id": e.get("actor_id"),
                    "correlation_id": e.get("correlation_id"),
                    "occurred_at": datetime.now(UTC),
                }
                for e in events
            ]
        )
        await self.db.execute(stmt)
