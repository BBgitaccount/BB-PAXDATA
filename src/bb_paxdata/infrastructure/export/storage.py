# src/bb_paxdata/infrastructure/export/storage.py
from __future__ import annotations

import boto3
import structlog
from botocore.client import Config
from botocore.exceptions import ClientError

from bb_paxdata.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class StorageManager:
    """Manages MinIO/S3 storage for export files with presigned URLs."""

    def __init__(self):
        self._client = None
        self._bucket_name = (
            settings.minio_bucket_name
            if hasattr(settings, "minio_bucket_name")
            else "exports"
        )

    @property
    def client(self):
        """Lazy initialization of S3 client."""
        if self._client is None:
            endpoint_url = getattr(settings, "minio_endpoint_url", None)
            access_key = getattr(settings, "minio_access_key", None)
            secret_key = getattr(settings, "minio_secret_key", None)

            if endpoint_url and access_key and secret_key:
                self._client = boto3.client(
                    "s3",
                    endpoint_url=endpoint_url,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    config=Config(signature_version="s3v4"),
                    region_name="us-east-1",
                )
            else:
                logger.warning(
                    "MinIO credentials not configured, using local storage fallback"
                )
                self._client = None
        return self._client

    def upload_export(
        self,
        job_id: str,
        file_bytes: bytes,
        content_type: str,
        filename: str | None = None,
        expires_in_hours: int = 24,
    ) -> str:
        """
        Upload export file to storage and return presigned download URL.

        Args:
            job_id: Export job ID
            file_bytes: File content as bytes
            content_type: MIME type (e.g., 'application/pdf')
            filename: Optional filename for the object
            expires_in_hours: URL expiration time in hours

        Returns:
            Presigned URL for download
        """
        if filename is None:
            filename = f"export_{job_id}.{self._get_extension(content_type)}"

        object_key = f"exports/{job_id}/{filename}"

        if self.client:
            try:
                self.client.put_object(
                    Bucket=self._bucket_name,
                    Key=object_key,
                    Body=file_bytes,
                    ContentType=content_type,
                )

                # Generate presigned URL
                url = self.client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket_name, "Key": object_key},
                    ExpiresIn=expires_in_hours * 3600,
                )

                logger.info("export_uploaded", job_id=job_id, object_key=object_key)
                return url

            except ClientError as e:
                logger.error("minio_upload_failed", job_id=job_id, error=str(e))
                raise StorageError(f"Failed to upload to MinIO: {e}")
        else:
            # Fallback to local storage for development
            import os

            local_dir = os.path.join(
                settings.output_dir if hasattr(settings, "output_dir") else "output",
                "exports",
            )
            os.makedirs(local_dir, exist_ok=True)
            local_path = os.path.join(local_dir, filename)

            with open(local_path, "wb") as f:
                f.write(file_bytes)

            logger.info("export_uploaded_local", job_id=job_id, path=local_path)
            return f"file://{local_path}"

    def delete_export(self, job_id: str, filename: str) -> bool:
        """Delete export file from storage."""
        object_key = f"exports/{job_id}/{filename}"

        if self.client:
            try:
                self.client.delete_object(Bucket=self._bucket_name, Key=object_key)
                logger.info("export_deleted", job_id=job_id, object_key=object_key)
                return True
            except ClientError as e:
                logger.error("minio_delete_failed", job_id=job_id, error=str(e))
                return False
        return False

    def _get_extension(self, content_type: str) -> str:
        """Map content type to file extension."""
        mapping = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/gexf+xml": "gexf",
            "application/xml": "gexf",
        }
        return mapping.get(content_type, "bin")


class StorageError(Exception):
    """Storage operation error."""

    pass
