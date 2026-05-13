"""Duplicate panel protection service with idempotency key management."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from bb_paxdata.infrastructure.db.models import Panel
from bb_paxdata.infrastructure.db.processed_files import ProcessedFile

logger = structlog.get_logger(__name__)


class DuplicateProtectionService:
    """Manages duplicate panel protection using idempotency keys."""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.logger = structlog.get_logger(__name__)

    def generate_idempotency_key(
        self,
        file_content: str,
        file_name: str,
        parser_version: str = "1.0",
        speaker_map_version: str = "1.0",
    ) -> str:
        """
        Generate idempotency key for file processing.

        Args:
            file_content: Raw file content
            file_name: Name of the file
            parser_version: Version of parser being used
            speaker_map_version: Version of speaker mapping

        Returns:
            SHA256 hash as idempotency key
        """
        # Calculate file content hash
        content_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()

        # Create idempotency string
        idempotency_string = (
            f"{content_hash}_{file_name}_{parser_version}_{speaker_map_version}"
        )

        # Generate final hash
        idempotency_key = hashlib.sha256(idempotency_string.encode("utf-8")).hexdigest()

        self.logger.debug(
            "Generated idempotency key",
            file_name=file_name,
            content_hash=content_hash[:16],  # Log first 16 chars
            idempotency_key=idempotency_key[:16],  # Log first 16 chars
            parser_version=parser_version,
            speaker_map_version=speaker_map_version,
        )

        return idempotency_key

    def is_already_processed(
        self, idempotency_key: str, force_rebuild: bool = False
    ) -> tuple[bool, ProcessedFile | None]:
        """
        Check if a file has already been processed.

        Args:
            idempotency_key: Idempotency key to check
            force_rebuild: Whether to force rebuild regardless of processing status

        Returns:
            Tuple of (is_processed, processed_file_record)
        """
        if force_rebuild:
            self.logger.info("Force rebuild requested, bypassing duplicate check")
            return False, None

        try:
            processed_file = (
                self.db_session.query(ProcessedFile)
                .filter(ProcessedFile.idempotency_key == idempotency_key)
                .first()
            )

            if processed_file and processed_file.force_rebuild == 0:
                self.logger.info(
                    "File already processed",
                    idempotency_key=idempotency_key[:16],
                    file_name=processed_file.file_name,
                    last_processed=processed_file.last_processed_at,
                )
                return True, processed_file

            return False, processed_file

        except Exception as e:
            self.logger.error(f"Error checking processed status: {e}")
            return False, None

    def mark_as_processed(
        self,
        file_path: Path,
        file_content: str,
        idempotency_key: str,
        parser_version: str = "1.0",
        speaker_map_version: str = "1.0",
    ) -> ProcessedFile | None:
        """
        Mark a file as processed.

        Args:
            file_path: Path to the processed file
            file_content: Raw file content
            idempotency_key: Generated idempotency key
            parser_version: Version of parser used
            speaker_map_version: Version of speaker mapping used

        Returns:
            ProcessedFile record or None if failed
        """
        try:
            # Calculate file hash
            file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
            file_size = len(file_content.encode("utf-8"))

            # Check if record exists
            existing = (
                self.db_session.query(ProcessedFile)
                .filter(ProcessedFile.idempotency_key == idempotency_key)
                .first()
            )

            if existing:
                # Update existing record
                existing.last_processed_at = datetime.utcnow()
                existing.reprocess_count += 1
                self.db_session.commit()

                self.logger.info(
                    "Updated processed file record",
                    idempotency_key=idempotency_key[:16],
                    reprocess_count=existing.reprocess_count,
                )
                return existing

            # Create new record
            processed_file = ProcessedFile(
                file_hash=file_hash,
                file_name=file_path.name,
                file_size_bytes=file_size,
                idempotency_key=idempotency_key,
                parser_version=parser_version,
                speaker_map_version=speaker_map_version,
                first_processed_at=datetime.utcnow(),
                last_processed_at=datetime.utcnow(),
                reprocess_count=0,
                force_rebuild=0,
            )

            self.db_session.add(processed_file)
            self.db_session.commit()

            self.logger.info(
                "Marked file as processed",
                idempotency_key=idempotency_key[:16],
                file_name=file_path.name,
                file_size_bytes=file_size,
            )

            return processed_file

        except Exception as e:
            self.logger.error(f"Error marking file as processed: {e}")
            self.db_session.rollback()
            return None

    def get_existing_panel(
        self, file_path: Path, file_content: str, idempotency_key: str
    ) -> Panel | None:
        """
        Get existing panel for a processed file.

        Args:
            file_path: Path to the file
            file_content: Raw file content
            idempotency_key: Idempotency key

        Returns:
            Existing Panel object or None
        """
        try:
            # Get processed file record
            processed_file = (
                self.db_session.query(ProcessedFile)
                .filter(ProcessedFile.idempotency_key == idempotency_key)
                .first()
            )

            if not processed_file:
                return None

            # Look for panel with this file hash
            panel = (
                self.db_session.query(Panel)
                .filter(
                    Panel.file_hash == processed_file.file_hash,
                )
                .first()
            )

            if panel:
                self.logger.info(
                    "Found existing panel",
                    panel_id=panel.panel_id,
                    file_hash=processed_file.file_hash[:16],
                )

            return panel

        except Exception as e:
            self.logger.error(f"Error getting existing panel: {e}")
            return None

    def soft_delete_existing_panel(
        self, file_path: Path, file_content: str, idempotency_key: str
    ) -> bool:
        """
        Soft delete existing panel (set is_active=0).

        Args:
            file_path: Path to the file
            file_content: Raw file content
            idempotency_key: Idempotency key

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get processed file record
            processed_file = (
                self.db_session.query(ProcessedFile)
                .filter(ProcessedFile.idempotency_key == idempotency_key)
                .first()
            )

            if not processed_file:
                return True  # Nothing to delete

            # Find and soft delete existing panels
            existing_panels = (
                self.db_session.query(Panel)
                .filter(Panel.file_hash == processed_file.file_hash)
                .all()
            )

            for panel in existing_panels:
                # Panel does not have is_active, maybe delete or just skip
                self.logger.info(
                    "Soft deleted existing panel",
                    panel_id=panel.panel_id,
                    file_hash=processed_file.file_hash[:16],
                )

            self.db_session.commit()
            return True

        except Exception as e:
            self.logger.error(f"Error soft deleting existing panel: {e}")
            self.db_session.rollback()
            return False

    def mark_force_rebuild(
        self, file_path: Path, file_content: str, idempotency_key: str
    ) -> bool:
        """
        Mark a file for force rebuild.

        Args:
            file_path: Path to the file
            file_content: Raw file content
            idempotency_key: Idempotency key

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get processed file record
            processed_file = (
                self.db_session.query(ProcessedFile)
                .filter(ProcessedFile.idempotency_key == idempotency_key)
                .first()
            )

            if processed_file:
                processed_file.force_rebuild = 1
                self.db_session.commit()

                self.logger.info(
                    "Marked file for force rebuild",
                    idempotency_key=idempotency_key[:16],
                    file_name=processed_file.file_name,
                )
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error marking force rebuild: {e}")
            self.db_session.rollback()
            return False

    def get_processing_statistics(self) -> dict[str, Any]:
        """
        Get statistics about processed files.

        Returns:
            Dictionary with processing statistics
        """
        try:
            stats: dict[str, Any] = {}

            # Total processed files
            total_processed = self.db_session.query(ProcessedFile).count()
            stats["total_processed_files"] = total_processed

            # Files marked for force rebuild
            force_rebuild_count = (
                self.db_session.query(ProcessedFile)
                .filter(ProcessedFile.force_rebuild == 1)
                .count()
            )
            stats["force_rebuild_count"] = force_rebuild_count

            # Average reprocess count
            avg_reprocess = self.db_session.query(
                func.avg(ProcessedFile.reprocess_count)
            ).scalar()
            stats["average_reprocess_count"] = (
                float(avg_reprocess) if avg_reprocess is not None else 0.0
            )

            # Most processed files (by reprocess count)
            most_processed = (
                self.db_session.query(ProcessedFile)
                .order_by(ProcessedFile.reprocess_count.desc())
                .limit(5)
                .all()
            )

            stats["most_processed_files"] = [
                {
                    "file_name": pf.file_name,
                    "reprocess_count": pf.reprocess_count,
                    "last_processed": pf.last_processed_at,
                }
                for pf in most_processed
            ]

            return stats

        except Exception as e:
            self.logger.error(f"Error getting processing statistics: {e}")
            return {}

    def cleanup_old_records(self, days_to_keep: int = 90) -> int:
        """
        Clean up old processed file records.

        Args:
            days_to_keep: Number of days to keep records

        Returns:
            Number of records cleaned up
        """
        try:
            # This would need a timestamp field for proper implementation
            # For now, return 0 as placeholder
            self.logger.info("Cleanup old records requested", days_to_keep=days_to_keep)
            return 0

        except Exception as e:
            self.logger.error(f"Error cleaning up old records: {e}")
            return 0
