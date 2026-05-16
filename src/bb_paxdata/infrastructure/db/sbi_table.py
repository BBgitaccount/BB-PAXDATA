from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base


class SpeakerPositionTable(Base):
    """SQLAlchemy model for persisting speaker positions (Phase 7 SBI)."""

    __tablename__ = "speaker_positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    speaker_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    analysis_id: Mapped[str | None] = mapped_column(
        ForeignKey("analyses.id"), index=True, nullable=True
    )

    # Wordfish latent position
    wordfish_theta: Mapped[float] = mapped_column(Float, nullable=False)

    # Wordscores calibrated position
    wordscores_t: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Linguistic metrics
    stance_density: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Composite Speaker-Based Index
    sbi: Mapped[float] = mapped_column(Float, index=True, nullable=False)

    # Wordshoal session deviation
    session_deviation: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Weights used for composite SBI
    alpha: Mapped[float] = mapped_column(Float, default=0.6)
    beta: Mapped[float] = mapped_column(Float, default=0.25)
    gamma: Mapped[float] = mapped_column(Float, default=0.15)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_sbi_session_speaker", "session_id", "speaker_id", unique=True),
    )
