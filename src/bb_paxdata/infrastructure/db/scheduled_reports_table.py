# src/bb_paxdata/infrastructure/db/scheduled_reports_table.py
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    pass


class ReportFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ScheduledReport(Base):
    """Scheduled report configuration for automated exports."""

    __tablename__ = "scheduled_reports"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    template_id: Mapped[str | None] = mapped_column(String, nullable=True)
    session_filter: Mapped[str | None] = mapped_column(Text, nullable=True)
    frequency: Mapped[str] = mapped_column(String, nullable=False)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_of_day: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, default="Europe/Istanbul")
    export_formats: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(String, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default="now()",
    )


class DistributionList(Base):
    """Email distribution list for scheduled reports with GDPR consent."""

    __tablename__ = "distribution_lists"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scheduled_report_id: Mapped[str] = mapped_column(
        String, ForeignKey("scheduled_reports.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_token: Mapped[str | None] = mapped_column(String, nullable=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    added_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default="now()",
    )


class ReportEmbedToken(Base):
    """JWT tokens for iframe embedding of scheduled reports."""

    __tablename__ = "report_embed_tokens"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scheduled_report_id: Mapped[str] = mapped_column(
        String, ForeignKey("scheduled_reports.id"), nullable=False
    )
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    allowed_origins: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(String, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default="now()",
    )
