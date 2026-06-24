# src/bb_paxdata/infrastructure/db/export_job_table.py
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    pass


class ExportType(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"
    GEXF = "gexf"


class ExportStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportJob(Base):
    """Model for tracking async export jobs with audit trail."""

    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    file_id: Mapped[str] = mapped_column(
        String, ForeignKey("files.file_id"), nullable=False, index=True
    )
    export_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, default=ExportStatus.QUEUED.value, nullable=False, index=True
    )
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    options: Mapped[dict | None] = mapped_column(Text, nullable=True)
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default="now()",
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Audit fields
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
