"""
Canonical Event Table Model
CORRECTED (E04-M-02): SQL-based authoritative storage (not Redis-only).
"""

from __future__ import annotations

import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base


class CanonicalEventTable(Base):
    """
    SQL table for CanonicalEvent persistence.

    Uses SQLAlchemy 2.0 async + Alembic for migrations.
    Redis is acceptable only as read-through cache, not primary store.
    """

    __tablename__ = "canonical_events"

    event_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_description: Mapped[str] = mapped_column(String(1024), nullable=False)
    first_mention: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    participating_actors: Mapped[list] = mapped_column(JSON, default=list)
    related_sessions: Mapped[list] = mapped_column(JSON, default=list)
