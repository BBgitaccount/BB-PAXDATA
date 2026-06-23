"""
SQLAlchemy ORM model for Correction Event table.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.correction_event import CorrectionEvent


class CorrectionEventORM(Base):
    """
    Append-only correction event table.

    Records human corrections to AI-generated analysis for learning purposes.
    Once created, records cannot be modified or deleted (append-only constraint).
    """

    __tablename__ = "correction_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    sentence_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    field_corrected: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    original_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    corrected_value: Mapped[dict | None] = mapped_column(JSON, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ai_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    corrector_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    context_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def to_domain_model(self) -> CorrectionEvent:
        """Convert ORM to domain model."""
        from bb_paxdata.application.domain.models.correction_event import (
            CorrectionEvent,
        )

        return CorrectionEvent(
            id=self.id,
            sentence_id=self.sentence_id,
            field_corrected=self.field_corrected,
            original_value=self.original_value,
            corrected_value=self.corrected_value,
            prompt_version=self.prompt_version,
            ai_confidence=self.ai_confidence,
            corrector_id=self.corrector_id,
            timestamp=self.timestamp,
            context_snapshot=self.context_snapshot,
        )

    @classmethod
    def from_domain_model(cls, event: CorrectionEvent) -> CorrectionEventORM:
        """Create ORM instance from domain model."""
        return cls(
            id=event.id,
            sentence_id=event.sentence_id,
            field_corrected=event.field_corrected,
            original_value=event.original_value,
            corrected_value=event.corrected_value,
            prompt_version=event.prompt_version,
            ai_confidence=event.ai_confidence,
            corrector_id=event.corrector_id,
            timestamp=event.timestamp,
            context_snapshot=event.context_snapshot,
        )


# Composite indexes for common query patterns
__table_args__ = (
    Index("idx_correction_field_prompt", "field_corrected", "prompt_version"),
    Index("idx_correction_timestamp_field", "timestamp", "field_corrected"),
    Index("idx_correction_corrector_timestamp", "corrector_id", "timestamp"),
)
