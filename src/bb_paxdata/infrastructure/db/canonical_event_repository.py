"""
Canonical Event SQL Repository Implementation
CORRECTED (E04-M-02): SQL-based authoritative storage with optional Redis cache.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.canonical_event import CanonicalEvent
from bb_paxdata.application.domain.ports.i_canonical_event_repository import (
    ICanonicalEventRepository,
)
from bb_paxdata.infrastructure.db.canonical_event_table import CanonicalEventTable

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.cache.base import CacheBackend


class SQLCanonicalEventRepository(ICanonicalEventRepository):
    """
    SQL repository for CanonicalEvent persistence.

    Uses SQLAlchemy 2.0 async for authoritative storage.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, event: CanonicalEvent) -> None:
        """Insert or update a canonical event."""
        stmt = select(CanonicalEventTable).where(
            CanonicalEventTable.event_id == event.event_id
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.mention_count = event.mention_count
            existing.participating_actors = event.participating_actors
            existing.related_sessions = event.related_sessions
        else:
            # Insert new
            db_event = CanonicalEventTable(
                event_id=event.event_id,
                event_type=event.event_type,
                canonical_description=event.canonical_description,
                first_mention=event.first_mention,
                mention_count=event.mention_count,
                participating_actors=event.participating_actors,
                related_sessions=event.related_sessions,
            )
            self._session.add(db_event)

        await self._session.commit()

    async def get_by_id(self, event_id: str) -> CanonicalEvent | None:
        """Retrieve a canonical event by ID."""
        stmt = select(CanonicalEventTable).where(
            CanonicalEventTable.event_id == event_id
        )
        result = await self._session.execute(stmt)
        db_event = result.scalar_one_or_none()

        if db_event:
            return self._to_domain(db_event)
        return None

    async def get_all(self) -> list[CanonicalEvent]:
        """Retrieve all canonical events."""
        stmt = select(CanonicalEventTable)
        result = await self._session.execute(stmt)
        db_events = result.scalars().all()
        return [self._to_domain(e) for e in db_events]

    async def get_by_session(self, session_id: str) -> list[CanonicalEvent]:
        """Retrieve all events related to a session."""
        stmt = select(CanonicalEventTable).where(
            CanonicalEventTable.related_sessions.contains(session_id)
        )
        result = await self._session.execute(stmt)
        db_events = result.scalars().all()
        return [self._to_domain(e) for e in db_events]

    async def get_by_event_type(self, event_type: str) -> list[CanonicalEvent]:
        """Retrieve all events of a specific type."""
        stmt = select(CanonicalEventTable).where(
            CanonicalEventTable.event_type == event_type
        )
        result = await self._session.execute(stmt)
        db_events = result.scalars().all()
        return [self._to_domain(e) for e in db_events]

    def _to_domain(self, db_event: CanonicalEventTable) -> CanonicalEvent:
        """Convert DB model to domain model."""
        return CanonicalEvent(
            canonical_description=db_event.canonical_description,
            first_mention=db_event.first_mention,
            event_type=db_event.event_type,
        )

    def _set_domain_fields(
        self, domain: CanonicalEvent, db_event: CanonicalEventTable
    ) -> None:
        """Set derived fields from DB to domain model."""
        domain.event_id = db_event.event_id
        domain.mention_count = db_event.mention_count
        domain.participating_actors = db_event.participating_actors
        domain.related_sessions = db_event.related_sessions


class CachedCanonicalEventRepository(ICanonicalEventRepository):
    """
    Cached repository wrapper with Redis read-through cache.

    Redis is used only as read-through cache for performance.
    SQL remains the authoritative source of truth.
    """

    def __init__(
        self,
        db_repo: ICanonicalEventRepository,
        cache: CacheBackend,
    ) -> None:
        self._db = db_repo
        self._cache = cache

    async def upsert(self, event: CanonicalEvent) -> None:
        """Insert or update a canonical event (bypass cache)."""
        await self._db.upsert(event)
        # Invalidate cache for this event
        await self._cache.delete(f"event:{event.event_id}")

    async def get_by_id(self, event_id: str) -> CanonicalEvent | None:
        """Retrieve a canonical event by ID with cache."""
        cached = await self._cache.get(f"event:{event_id}")
        if cached:
            try:
                data = json.loads(cached)
                event = CanonicalEvent(
                    canonical_description=data["canonical_description"],
                    first_mention=data["first_mention"],
                    event_type=data["event_type"],
                )
                event.event_id = data["event_id"]
                event.mention_count = data["mention_count"]
                event.participating_actors = data["participating_actors"]
                event.related_sessions = data["related_sessions"]
                return event
            except (json.JSONDecodeError, KeyError):
                pass  # Cache miss or corrupted, fall through to DB

        result = await self._db.get_by_id(event_id)
        if result:
            await self._cache.set(
                f"event:{event_id}",
                json.dumps(
                    {
                        "event_id": result.event_id,
                        "event_type": result.event_type,
                        "canonical_description": result.canonical_description,
                        "first_mention": result.first_mention.isoformat(),
                        "mention_count": result.mention_count,
                        "participating_actors": result.participating_actors,
                        "related_sessions": result.related_sessions,
                    }
                ),
                ttl=3600,
            )
        return result

    async def get_all(self) -> list[CanonicalEvent]:
        """Retrieve all canonical events (bypass cache)."""
        return await self._db.get_all()

    async def get_by_session(self, session_id: str) -> list[CanonicalEvent]:
        """Retrieve all events related to a session (bypass cache)."""
        return await self._db.get_by_session(session_id)

    async def get_by_event_type(self, event_type: str) -> list[CanonicalEvent]:
        """Retrieve all events of a specific type (bypass cache)."""
        return await self._db.get_by_event_type(event_type)
