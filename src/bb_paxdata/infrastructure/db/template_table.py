# src/bb_paxdata/infrastructure/db/template_table.py
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


class TemplateCategory(str, Enum):
    CUSTOM = "custom"
    UN_SECURITY_COUNCIL = "un_security_council"
    BILATERAL = "bilateral"
    PERIODIC = "periodic"
    COMPARATIVE = "comparative"


class OutputFormat(str, Enum):
    PDF_LATEX = "pdf_latex"
    HTML = "html"
    MARKDOWN = "markdown"


class ReportTemplate(Base):
    """Report template with versioning support."""

    __tablename__ = "report_templates"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(String, nullable=False)
    variables_used: Mapped[dict | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(String, default=False)
    is_system: Mapped[bool] = mapped_column(String, default=False)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default="now()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default="now()",
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )


class ReportTemplateVersion(Base):
    """Template version history for rollback capability."""

    __tablename__ = "report_template_versions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    template_id: Mapped[str] = mapped_column(
        String, ForeignKey("report_templates.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default="now()",
    )
