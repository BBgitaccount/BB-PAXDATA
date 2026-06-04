# src/bb_paxdata/infrastructure/db/models/outbox.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from bb_paxdata.infrastructure.db.base import Base
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text


class OutboxEventORM(Base):
    __tablename__ = "outbox_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(100), nullable=False, index=True)
    aggregate_id = Column(
        String(36), nullable=False, index=True
    )  # analysis_id, segment_id vb.
    payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed = Column(Boolean, default=False, index=True)
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)


class DeadLetterEventORM(Base):
    """
    MaxRetry aşımı veya kalıcı hata sonucu işlenemeyen event'ler buraya taşınır.
    Manuel inceleme ve yeniden işleme için korunur.
    """

    __tablename__ = "dead_letter_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_event_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    failure_reason = Column(Text, nullable=False)
    moved_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved = Column(Boolean, default=False)
