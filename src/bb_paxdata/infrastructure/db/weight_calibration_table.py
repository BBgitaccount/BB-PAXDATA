"""
SQLAlchemy ORM models for weight calibration.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.weight_calibration import (
        CalibratableParameter,
        WeightUpdateProposal,
    )


class SQLEnum(Enum):
    """SQLAlchemy Enum for parameter types and proposal status."""

    SENTIMENT_WEIGHT = "sentiment_weight"
    RISK_THRESHOLD = "risk_threshold"
    HEDGING_WEIGHT = "hedging_weight"
    WORDFISH_SMOOTHING = "wordfish_smoothing"


class SQLProposalStatus(Enum):
    """SQLAlchemy Enum for proposal status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVATED = "activated"
    ROLLED_BACK = "rolled_back"


class CalibratableParameterORM(Base):
    """ORM for calibratable parameters."""

    __tablename__ = "calibratable_parameters"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    parameter_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    min_value: Mapped[float] = mapped_column(Float, nullable=False)
    max_value: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    version: Mapped[int] = mapped_column(default=1)

    def to_domain_model(self) -> CalibratableParameter:
        from bb_paxdata.application.domain.models.weight_calibration import (
            CalibratableParameter,
            ParameterType,
        )

        return CalibratableParameter(
            id=self.id,
            name=self.name,
            parameter_type=ParameterType(self.parameter_type),
            current_value=self.current_value,
            min_value=self.min_value,
            max_value=self.max_value,
            description=self.description or "",
            last_updated=self.last_updated,
            version=self.version,
        )


class WeightUpdateProposalORM(Base):
    """ORM for weight update proposals."""

    __tablename__ = "weight_update_proposals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    parameter_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parameter_name: Mapped[str] = mapped_column(String(255), nullable=False)
    old_value: Mapped[float] = mapped_column(Float, nullable=False)
    proposed_value: Mapped[float] = mapped_column(Float, nullable=False)
    correction_signal: Mapped[float] = mapped_column(Float, nullable=False)
    learning_rate: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rollback_version: Mapped[int | None] = mapped_column(nullable=True)

    def to_domain_model(self) -> WeightUpdateProposal:
        from bb_paxdata.application.domain.models.weight_calibration import (
            ProposalStatus,
            WeightUpdateProposal,
        )

        return WeightUpdateProposal(
            id=self.id,
            parameter_id=self.parameter_id,
            parameter_name=self.parameter_name,
            old_value=self.old_value,
            proposed_value=self.proposed_value,
            correction_signal=self.correction_signal,
            learning_rate=self.learning_rate,
            confidence=self.confidence,
            reason=self.reason,
            created_at=self.created_at,
            status=ProposalStatus(self.status),
            approved_by=self.approved_by,
            approved_at=self.approved_at,
            activated_at=self.activated_at,
            rollback_version=self.rollback_version,
        )


class WeightVersionHistoryORM(Base):
    """ORM for weight version history."""

    __tablename__ = "weight_version_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    parameter_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    proposal_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )


# Indexes
__table_args__ = (
    Index("idx_proposal_parameter_status", "parameter_id", "status"),
    Index("idx_proposal_created_status", "created_at", "status"),
    Index("idx_history_parameter_version", "parameter_id", "version"),
)
