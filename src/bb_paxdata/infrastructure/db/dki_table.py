from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base


class DKIResultModel(Base):
    """SQLAlchemy table for DKI (Discourse-Kinetic Index) results.

    Stores the composite score and its three primary components for longitudinal analysis.
    """

    __tablename__ = "dki_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("analyses.id"), index=True
    )
    speaker_id: Mapped[str] = mapped_column(String(50), index=True)
    session_id: Mapped[str] = mapped_column(String(50), index=True)

    # Core scores
    dki_score: Mapped[float] = mapped_column(Float)
    velocity: Mapped[float] = mapped_column(Float)
    semantic_shift: Mapped[float] = mapped_column(Float)
    debate_loading: Mapped[float] = mapped_column(Float)

    # Anomaly tracking
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    calculation_method: Mapped[str] = mapped_column(String(100), default="dki_v1.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<DKIResultModel(speaker={self.speaker_id}, score={self.dki_score})>"
