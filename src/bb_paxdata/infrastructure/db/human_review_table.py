"""SQLAlchemy 2.0 ORM: human_reviews ve calibration_reports tabloları."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base


class HumanReviewORM(Base):
    __tablename__ = "human_reviews"
    __table_args__ = (
        Index("idx_review_status_created", "agreement_status", "created_at"),
        Index("idx_review_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True, comment="FK -> ai_sentence_analyses.id"
    )
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # AI referans skorları (salt okunur)
    ai_sbi_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_dominant_frame: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # İnsan düzeltmeleri
    human_sbi_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_dominant_frame: Mapped[str | None] = mapped_column(String(100), nullable=True)
    human_risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    human_sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Meta
    agreement_status: Mapped[str] = mapped_column(String(20), nullable=False)
    disagreement_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    # Computed flags (SQLite'da GENERATED ALWAYS AS yoktur; uygulama katmanında hesapla)
    has_frame_disagreement: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_risk_disagreement: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sbi_delta: Mapped[float | None] = mapped_column(Float, nullable=True)


class CalibrationReportORM(Base):
    __tablename__ = "calibration_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    evaluation_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    evaluation_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    cohens_kappa_frame: Mapped[float | None] = mapped_column(Float, nullable=True)
    cohens_kappa_risk: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_human_f1_frame: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_human_f1_risk: Mapped[float | None] = mapped_column(Float, nullable=True)
    sbi_mae: Mapped[float | None] = mapped_column(Float, nullable=True)

    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_disagreements: Mapped[int] = mapped_column(Integer, default=0)
    top_disagreement_patterns: Mapped[str | None] = mapped_column(
        JSON, nullable=True, comment="En sık anlaşmazlık patternları listesi"
    )

    requires_prompt_update: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_weight_update: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
