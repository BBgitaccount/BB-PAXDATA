# src/bb_paxdata/infrastructure/db/model_evaluation.py
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bb_paxdata.infrastructure.db.base import Base


class ModelEvaluationRun(Base):
    __tablename__ = "model_evaluation_runs"

    run_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"eval-{uuid.uuid4().hex[:12]}",
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    prompt_version_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    dataset_version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float)
    p95_latency_ms: Mapped[float | None] = mapped_column(Float)
    p99_latency_ms: Mapped[float | None] = mapped_column(Float)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    status: Mapped[str] = mapped_column(
        String(16), default="running"
    )  # running | completed | failed

    metrics: Mapped[list[ModelEvaluationMetric]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_eval_model_dataset", "model_name", "dataset_version_hash"),
    )


class ModelEvaluationMetric(Base):
    __tablename__ = "model_evaluation_metrics"

    metric_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("model_evaluation_runs.run_id", ondelete="CASCADE"), index=True
    )
    sentence_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Semantic similarity (SBERT cosine between prediction and gold)
    cosine_similarity: Mapped[float | None] = mapped_column(Float)

    # Classification exact match
    sentiment_match: Mapped[bool | None] = mapped_column(nullable=True)
    risk_match: Mapped[bool | None] = mapped_column(nullable=True)
    frame_match: Mapped[bool | None] = mapped_column(nullable=True)

    # Regression error
    risk_mae: Mapped[float | None] = mapped_column(Float)
    sbi_mae: Mapped[float | None] = mapped_column(Float)

    # Raw outputs for audit
    predicted_summary: Mapped[str | None] = mapped_column(nullable=True)
    gold_summary: Mapped[str | None] = mapped_column(nullable=True)

    run: Mapped[ModelEvaluationRun] = relationship(
        back_populates="metrics", lazy="joined"
    )


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    audit_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
