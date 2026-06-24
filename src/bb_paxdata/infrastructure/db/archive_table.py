"""
Database table for archive metadata (TASK-1.3.2)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.application.domain.models.retention import ArchiveStatus, DataType
from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    pass


class ArchiveMetadataORM(Base):
    """
    ORM model for archive metadata.
    """

    __tablename__ = "archive_metadata"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    archive_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    original_record_ids: Mapped[str] = mapped_column(Text, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    archived_by: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=ArchiveStatus.PENDING.value, nullable=False, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_archive_data_type_status", "data_type", "status"),
        Index("idx_archive_archived_at", "archived_at"),
    )

    def to_domain(self) -> dict:
        """Convert to domain model dictionary."""
        import json

        from bb_paxdata.application.domain.models.retention import ArchiveMetadata

        return ArchiveMetadata(
            archive_id=self.archive_id,
            data_type=DataType(self.data_type),
            original_record_ids=json.loads(self.original_record_ids),
            archived_at=self.archived_at,
            archived_by=self.archived_by,
            file_path=self.file_path,
            file_size_bytes=self.file_size_bytes,
            checksum=self.checksum,
            status=ArchiveStatus(self.status),
            error_message=self.error_message,
            metadata=json.loads(self.metadata_json) if self.metadata_json else None,
        ).to_dict()
