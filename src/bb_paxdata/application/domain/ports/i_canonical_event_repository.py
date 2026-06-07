"""
Canonical Event Repository Protocol
CORRECTED (E04-M-02): SQL-based repository pattern (not Redis-only).
"""

from __future__ import annotations

from typing import Protocol

from bb_paxdata.application.domain.models.canonical_event import CanonicalEvent


class ICanonicalEventRepository(Protocol):
    """
    Repository protocol for CanonicalEvent persistence.

    Uses SQL as authoritative storage (Alembic + SQLAlchemy 2.0 async).
    Redis is acceptable only as read-through cache, not primary store.
    """

    async def upsert(self, event: CanonicalEvent) -> None:
        """Insert or update a canonical event."""
        ...

    async def get_by_id(self, event_id: str) -> CanonicalEvent | None:
        """Retrieve a canonical event by ID."""
        ...

    async def get_all(self) -> list[CanonicalEvent]:
        """Retrieve all canonical events."""
        ...

    async def get_by_session(self, session_id: str) -> list[CanonicalEvent]:
        """Retrieve all events related to a session."""
        ...

    async def get_by_event_type(self, event_type: str) -> list[CanonicalEvent]:
        """Retrieve all events of a specific type."""
        ...
