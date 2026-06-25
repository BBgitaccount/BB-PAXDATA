"""
Data Retention and Archiving Domain Models (TASK-1.3)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class DataType(StrEnum):
    """Types of data subject to retention policies."""

    RAW_TRANSCRIPT = "raw_transcript"
    AI_ANALYSIS = "ai_analysis"
    ANONYMIZED_STATISTICS = "anonymized_statistics"
    HITL_CORRECTIONS = "hitl_corrections"
    AUDIT_LOG = "audit_log"


class ArchiveStatus(StrEnum):
    """Status of archive operations."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORED = "restored"


@dataclass
class RetentionPolicy:
    """
    Retention policy for a specific data type.
    """

    data_type: DataType
    retention_years: int
    permanent: bool = False
    archive_before_deletion: bool = True

    def is_expired(self, created_at: datetime) -> bool:
        """Check if data has exceeded retention period."""
        if self.permanent:
            return False

        if self.retention_years == 0:
            return False

        expiry_date = created_at.replace(year=created_at.year + self.retention_years)
        return datetime.now(UTC) > expiry_date


@dataclass
class ArchiveMetadata:
    """
    Metadata for archived data.
    """

    archive_id: str
    data_type: DataType
    original_record_ids: list[str]
    archived_at: datetime
    archived_by: str
    file_path: str
    file_size_bytes: int
    checksum: str
    status: ArchiveStatus = ArchiveStatus.PENDING
    error_message: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "archive_id": self.archive_id,
            "data_type": self.data_type.value,
            "original_record_ids": self.original_record_ids,
            "archived_at": self.archived_at.isoformat(),
            "archived_by": self.archived_by,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "checksum": self.checksum,
            "status": self.status.value,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class PIIMaskingResult:
    """
    Result of PII masking operation.
    """

    original_text: str
    masked_text: str
    detected_entities: list[dict[str, Any]]
    speaker_mapping: dict[str, str]  # original_id -> encoded_id
    location_mapping: dict[str, str]  # original_location -> generalized_location
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "original_text": self.original_text,
            "masked_text": self.masked_text,
            "detected_entities": self.detected_entities,
            "speaker_mapping": self.speaker_mapping,
            "location_mapping": self.location_mapping,
            "timestamp": self.timestamp.isoformat(),
        }
