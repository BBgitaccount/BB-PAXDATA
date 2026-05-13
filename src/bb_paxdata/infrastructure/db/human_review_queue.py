"""Human review queue model for HIGH/CRITICAL risk sentences."""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    pass


class HumanReviewQueue(Base):
    """Tracks sentences requiring human review."""

    __tablename__ = "ai_human_review_queue"

    review_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    sent_id: Mapped[str] = mapped_column(String, nullable=False)
    seg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    panel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Trigger reason
    trigger_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 'HIGH_RISK' | 'CRITICAL_ANOMALY' | 'LOW_UNCERTAINTY' | 'MANUAL_FLAG'
    ai_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anomaly_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    uncertainty_score: Mapped[float | None] = mapped_column(Integer, nullable=True)

    # State machine
    status: Mapped[str] = mapped_column(
        String, default="PENDING"
    )  # PENDING, ASSIGNED, IN_REVIEW, APPROVED, REJECTED, MODIFIED, ESCALATED
    assigned_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI original output
    original_ai_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Human correction (if any)
    corrected_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    flagged_at: Mapped[str | None] = mapped_column(
        Text, server_default=func.now(), nullable=True
    )
    reviewed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
