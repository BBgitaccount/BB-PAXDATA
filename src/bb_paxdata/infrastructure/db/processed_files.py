"""Processed files tracking model for duplicate protection."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    pass


class ProcessedFile(Base):
    """Tracks processed files to prevent duplicate processing."""

    __tablename__ = "processed_files"

    file_hash: Mapped[str] = mapped_column(String, primary_key=True)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker_map_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_processed_at: Mapped[datetime | None] = mapped_column(
        Text, server_default=func.now(), nullable=True
    )
    last_processed_at: Mapped[datetime | None] = mapped_column(Text, nullable=True)
    reprocess_count: Mapped[int] = mapped_column(Integer, default=0)
    force_rebuild: Mapped[int] = mapped_column(Integer, default=0)
