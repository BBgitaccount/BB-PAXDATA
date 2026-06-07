from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.application.domain.models.sbi_models import SpeakerPosition
from bb_paxdata.infrastructure.db.base import Base


class SpeakerPositionTable(Base):
    """SQLAlchemy model for persisting speaker positions (Phase 7 SBI)."""

    __tablename__ = "speaker_positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    speaker_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    analysis_id: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
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
    delta: Mapped[float] = mapped_column(Float, default=0.05)
    gat_anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    __table_args__ = (
        Index("ix_sbi_session_speaker", "session_id", "speaker_id", unique=True),
    )

    def to_domain(self) -> SpeakerPosition:
        """Convert ORM model to domain model."""
        return SpeakerPosition(
            speaker_id=self.speaker_id,
            session_id=self.session_id,
            wordfish_theta=self.wordfish_theta,
            wordscores_t=self.wordscores_t,
            stance_density=self.stance_density,
            engagement_score=self.engagement_score,
            sbi=self.sbi,
            session_deviation=self.session_deviation,
            alpha=self.alpha,
            beta=self.beta,
            gamma=self.gamma,
            delta=self.delta,
            gat_anomaly_score=self.gat_anomaly_score,
            computed_at=(
                self.computed_at.replace(tzinfo=timezone.utc)
                if self.computed_at.tzinfo is None
                else self.computed_at
            ),
        )
