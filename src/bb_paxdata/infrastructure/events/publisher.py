"""Append-only domain event publisher."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.models import DomainEvent


class WORMEventPublisher:
    """Writes immutable domain events to the WORM event store.

    Usage:
        publisher = WORMEventPublisher(db)
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
        from bb_paxdata.infrastructure.events.upcaster import global_upcaster_registry

        latest_version = global_upcaster_registry.get_latest_version(event_type)

        event = DomainEvent(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            event_version=latest_version,
            payload=payload,
            actor_id=actor_id,
            correlation_id=correlation_id,
            occurred_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(event)

        # Generate OutboxEventORM for active subscriptions
        from sqlalchemy import select

        from bb_paxdata.infrastructure.db.models import (
            OutboxEventORM,
            WebhookSubscriptionORM,
        )

        stmt = select(WebhookSubscriptionORM).where(WebhookSubscriptionORM.is_active)
        result = await self.db.execute(stmt)
        subscriptions = result.scalars().all()

        for sub in subscriptions:
            if "*" in sub.event_types or event_type in sub.event_types:
                outbox_event = OutboxEventORM(
                    event_type=event_type,
                    event_version=latest_version,
                    aggregate_id=aggregate_id,
                    payload=payload,
                    endpoint_url=sub.endpoint_url,
                    secret=sub.secret,
                    endpoint_id=sub.id,
                )
                self.db.add(outbox_event)

    async def emit_batch(self, events: list[dict[str, Any]]) -> None:
        """Bulk emit multiple events in a single transaction."""
        if not events:
            return
        from bb_paxdata.infrastructure.events.upcaster import global_upcaster_registry

        stmt = insert(DomainEvent).values(
            [
                {
                    "aggregate_type": e["aggregate_type"],
                    "aggregate_id": e["aggregate_id"],
                    "event_type": e["event_type"],
                    "event_version": global_upcaster_registry.get_latest_version(
                        e["event_type"]
                    ),
                    "payload": e["payload"],
                    "actor_id": e.get("actor_id"),
                    "correlation_id": e.get("correlation_id"),
                    "occurred_at": datetime.now(UTC).replace(tzinfo=None),
                }
                for e in events
            ]
        )
        await self.db.execute(stmt)

        # Generate OutboxEventORM for active subscriptions
        from sqlalchemy import select

        from bb_paxdata.infrastructure.db.models import (
            OutboxEventORM,
            WebhookSubscriptionORM,
        )

        sub_stmt = select(WebhookSubscriptionORM).where(
            WebhookSubscriptionORM.is_active
        )
        result = await self.db.execute(sub_stmt)
        subscriptions = result.scalars().all()

        outbox_records = []
        for e in events:
            evt_type = e["event_type"]
            agg_id = e["aggregate_id"]
            payl = e["payload"]
            evt_ver = global_upcaster_registry.get_latest_version(evt_type)

            for sub in subscriptions:
                if "*" in sub.event_types or evt_type in sub.event_types:
                    outbox_records.append(
                        OutboxEventORM(
                            event_type=evt_type,
                            event_version=evt_ver,
                            aggregate_id=agg_id,
                            payload=payl,
                            endpoint_url=sub.endpoint_url,
                            secret=sub.secret,
                            endpoint_id=sub.id,
                        )
                    )
        if outbox_records:
            self.db.add_all(outbox_records)
