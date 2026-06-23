"""
Data Retention and Archiving Service (TASK-1.3)
"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from bb_paxdata.application.domain.models.retention import (
    ArchiveMetadata,
    ArchiveStatus,
    DataType,
    RetentionPolicy,
)
from bb_paxdata.config.settings import get_settings


class RetentionService:
    """
    Service for managing data retention policies and archiving.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._policies: dict[DataType, RetentionPolicy] = self._init_policies()

    def _init_policies(self) -> dict[DataType, RetentionPolicy]:
        """Initialize retention policies from configuration."""
        config = self._settings.retention_policy
        return {
            DataType.RAW_TRANSCRIPT: RetentionPolicy(
                data_type=DataType.RAW_TRANSCRIPT,
                retention_years=config.raw_transcript_retention_years,
                permanent=False,
                archive_before_deletion=config.archive_after_retention,
            ),
            DataType.AI_ANALYSIS: RetentionPolicy(
                data_type=DataType.AI_ANALYSIS,
                retention_years=config.ai_analysis_retention_years,
                permanent=False,
                archive_before_deletion=config.archive_after_retention,
            ),
            DataType.ANONYMIZED_STATISTICS: RetentionPolicy(
                data_type=DataType.ANONYMIZED_STATISTICS,
                retention_years=0,
                permanent=config.anonymized_statistics_permanent,
                archive_before_deletion=False,
            ),
            DataType.HITL_CORRECTIONS: RetentionPolicy(
                data_type=DataType.HITL_CORRECTIONS,
                retention_years=0,
                permanent=config.hitl_corrections_permanent,
                archive_before_deletion=False,
            ),
            DataType.AUDIT_LOG: RetentionPolicy(
                data_type=DataType.AUDIT_LOG,
                retention_years=7,
                permanent=False,
                archive_before_deletion=True,
            ),
        }

    def get_policy(self, data_type: DataType) -> RetentionPolicy:
        """Get retention policy for a data type."""
        return self._policies.get(data_type, RetentionPolicy(data_type, 0, True))

    def is_expired(self, data_type: DataType, created_at: datetime) -> bool:
        """Check if data has expired according to retention policy."""
        policy = self.get_policy(data_type)
        return policy.is_expired(created_at)

    def get_expiry_date(
        self, data_type: DataType, created_at: datetime
    ) -> datetime | None:
        """Get expiry date for data according to retention policy."""
        policy = self.get_policy(data_type)
        if policy.permanent or policy.retention_years == 0:
            return None
        return created_at.replace(year=created_at.year + policy.retention_years)


class ArchiveService:
    """
    Service for archiving data to S3/MinIO and restoring from archives.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._config = self._settings.archive
        self._s3_client = self._init_s3_client()

    def _init_s3_client(self) -> Any:
        """Initialize S3/MinIO client."""
        return boto3.client(
            "s3",
            endpoint_url=self._config.s3_endpoint_url,
            aws_access_key_id=self._config.s3_access_key,
            aws_secret_access_key=self._config.s3_secret_key.get_secret_value(),
            region_name=self._config.s3_region,
        )

    def _ensure_bucket_exists(self) -> None:
        """Ensure S3 bucket exists, create if not."""
        try:
            self._s3_client.head_bucket(Bucket=self._config.s3_bucket_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                self._s3_client.create_bucket(Bucket=self._config.s3_bucket_name)

    def _compute_checksum(self, data: bytes) -> str:
        """Compute SHA-256 checksum of data."""
        return hashlib.sha256(data).hexdigest()

    def _compress_data(self, data: bytes) -> bytes:
        """Compress data with gzip if enabled."""
        if self._config.archive_compression:
            return gzip.compress(data)
        return data

    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data with AES-256 if enabled."""
        if self._config.archive_encryption_enabled:
            from cryptography.fernet import Fernet

            key = self._config.archive_encryption_key.get_secret_value()
            if not key:
                raise ValueError("Encryption enabled but no key provided")
            fernet = Fernet(key.encode())
            return fernet.encrypt(data)
        return data

    def _decrypt_data(self, data: bytes) -> bytes:
        """Decrypt data with AES-256 if enabled."""
        if self._config.archive_encryption_enabled:
            from cryptography.fernet import Fernet

            key = self._config.archive_encryption_key.get_secret_value()
            if not key:
                raise ValueError("Encryption enabled but no key provided")
            fernet = Fernet(key.encode())
            return fernet.decrypt(data)
        return data

    def _decompress_data(self, data: bytes) -> bytes:
        """Decompress data with gzip if compression was used."""
        if self._config.archive_compression:
            return gzip.decompress(data)
        return data

    def archive_data(
        self,
        archive_id: str,
        data_type: DataType,
        data: dict[str, Any] | list[Any],
        metadata: dict[str, Any] | None = None,
    ) -> ArchiveMetadata:
        """
        Archive data to S3/MinIO.

        Args:
            archive_id: Unique identifier for the archive
            data_type: Type of data being archived
            data: Data to archive (dict or list)
            metadata: Additional metadata

        Returns:
            ArchiveMetadata with archive details
        """
        self._ensure_bucket_exists()

        # Serialize data to JSON
        json_data = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")

        # Compress and encrypt
        processed_data = self._compress_data(json_data)
        processed_data = self._encrypt_data(processed_data)

        # Compute checksum
        checksum = self._compute_checksum(processed_data)

        # Generate S3 key
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        s3_key = f"{data_type.value}/{timestamp}_{archive_id}.archive"

        # Upload to S3
        try:
            self._s3_client.put_object(
                Bucket=self._config.s3_bucket_name,
                Key=s3_key,
                Body=processed_data,
                Metadata={
                    "archive_id": archive_id,
                    "data_type": data_type.value,
                    "checksum": checksum,
                    **(metadata or {}),
                },
            )
        except ClientError as e:
            return ArchiveMetadata(
                archive_id=archive_id,
                data_type=data_type,
                original_record_ids=[],
                archived_at=datetime.now(timezone.utc),
                archived_by="system",
                file_path=s3_key,
                file_size_bytes=0,
                checksum="",
                status=ArchiveStatus.FAILED,
                error_message=str(e),
                metadata=metadata,
            )

        return ArchiveMetadata(
            archive_id=archive_id,
            data_type=data_type,
            original_record_ids=[],
            archived_at=datetime.now(timezone.utc),
            archived_by="system",
            file_path=s3_key,
            file_size_bytes=len(processed_data),
            checksum=checksum,
            status=ArchiveStatus.COMPLETED,
            metadata=metadata,
        )

    def restore_archive(
        self, archive_id: str, s3_key: str
    ) -> dict[str, Any] | list[Any]:
        """
        Restore archived data from S3/MinIO.

        Args:
            archive_id: Archive identifier
            s3_key: S3 object key

        Returns:
            Restored data (dict or list)
        """
        try:
            response = self._s3_client.get_object(
                Bucket=self._config.s3_bucket_name,
                Key=s3_key,
            )
            data = response["Body"].read()

            # Decrypt and decompress
            data = self._decrypt_data(data)
            data = self._decompress_data(data)

            # Deserialize JSON
            return json.loads(data.decode("utf-8"))
        except ClientError as e:
            raise RuntimeError(f"Failed to restore archive {archive_id}: {e}") from e

    def list_archives(
        self, data_type: DataType | None = None, prefix: str | None = None
    ) -> list[dict[str, Any]]:
        """
        List available archives.

        Args:
            data_type: Filter by data type
            prefix: Additional prefix filter

        Returns:
            List of archive metadata
        """
        prefix = f"{data_type.value}/" if data_type else prefix
        if not prefix:
            prefix = ""

        try:
            response = self._s3_client.list_objects_v2(
                Bucket=self._config.s3_bucket_name, Prefix=prefix
            )
            archives = []
            for obj in response.get("Contents", []):
                archives.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                    }
                )
            return archives
        except ClientError as e:
            raise RuntimeError(f"Failed to list archives: {e}") from e

    def delete_archive(self, s3_key: str) -> bool:
        """
        Delete an archive from S3/MinIO.

        Args:
            s3_key: S3 object key

        Returns:
            True if deleted successfully
        """
        try:
            self._s3_client.delete_object(
                Bucket=self._config.s3_bucket_name,
                Key=s3_key,
            )
            return True
        except ClientError as e:
            raise RuntimeError(f"Failed to delete archive {s3_key}: {e}") from e
