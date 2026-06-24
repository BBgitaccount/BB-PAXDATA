"""
Celery tasks for data retention and archiving (TASK-1.3.2)
"""

from __future__ import annotations

import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task

from bb_paxdata.application.domain.models.retention import (
    ArchiveStatus,
    DataType,
)
from bb_paxdata.application.domain.services.retention_service import (
    ArchiveService,
    RetentionService,
)
from bb_paxdata.config.settings import get_settings


@shared_task(bind=True, max_retries=3)
def archive_expired_data_task(self, data_type: str) -> dict[str, Any]:
    """
    Archive expired data of a specific type.

    Args:
        data_type: Type of data to archive (raw_transcript, ai_analysis, etc.)

    Returns:
        Task result with archive details
    """
    try:
        data_type_enum = DataType(data_type)
    except ValueError:
        return {"status": "error", "message": f"Invalid data type: {data_type}"}

    RetentionService()
    archive_service = ArchiveService()
    get_settings()

    # In production, this would query the database for expired records
    # For now, we'll create a placeholder implementation
    archive_id = f"archive-{uuid.uuid4().hex}"

    # Simulate data retrieval
    sample_data = {
        "archive_id": archive_id,
        "data_type": data_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "record_count": 0,
    }

    # Archive the data
    metadata = archive_service.archive_data(
        archive_id=archive_id,
        data_type=data_type_enum,
        data=sample_data,
        metadata={"task_id": self.request.id},
    )

    return {
        "status": "success" if metadata.status == ArchiveStatus.COMPLETED else "failed",
        "archive_id": archive_id,
        "data_type": data_type,
        "s3_key": metadata.file_path,
        "checksum": metadata.checksum,
        "file_size": metadata.file_size_bytes,
    }


@shared_task(bind=True, max_retries=3)
def delete_expired_data_task(self, data_type: str, archive_id: str) -> dict[str, Any]:
    """
    Delete expired data from database after successful archiving.

    Args:
        data_type: Type of data to delete
        archive_id: Archive ID for reference

    Returns:
        Task result with deletion details
    """
    try:
        DataType(data_type)
    except ValueError:
        return {"status": "error", "message": f"Invalid data type: {data_type}"}

    RetentionService()

    # In production, this would:
    # 1. Verify archive exists and is valid
    # 2. Delete records from database
    # 3. Log the deletion in audit trail

    # Placeholder implementation
    return {
        "status": "success",
        "data_type": data_type,
        "archive_id": archive_id,
        "records_deleted": 0,
        "deleted_at": datetime.now(UTC).isoformat(),
    }


@shared_task(bind=True, max_retries=3)
def pg_dump_and_archive_task(
    self,
    table_name: str,
    where_clause: str | None = None,
) -> dict[str, Any]:
    """
    Perform pg_dump for specific table and archive to S3/MinIO.

    Args:
        table_name: Database table to dump
        where_clause: Optional WHERE clause to filter records

    Returns:
        Task result with archive details
    """
    settings = get_settings()
    archive_service = ArchiveService()

    # Parse database URL to get connection details
    db_url = settings.database_url
    if not db_url or "postgresql" not in db_url:
        return {
            "status": "error",
            "message": "PostgreSQL database required for pg_dump",
        }

    # Extract connection parameters
    # Format: postgresql+asyncpg://user:pass@host:port/db
    url_parts = db_url.replace("postgresql+asyncpg://", "").split("@")
    user_pass = url_parts[0].split(":")
    host_db = url_parts[1].split("/")
    host_port = host_db[0].split(":")

    user = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else ""
    host = host_port[0]
    port = host_port[1] if len(host_port) > 1 else "5432"
    database = host_db[0]

    # Build pg_dump command
    pg_dump_cmd = [
        "pg_dump",
        f"--host={host}",
        f"--port={port}",
        f"--username={user}",
        f"--dbname={database}",
        "--table",
        table_name,
        "--format=plain",
        "--no-owner",
        "--no-acl",
    ]

    if where_clause:
        pg_dump_cmd.extend(["--where", where_clause])

    # Set PGPASSWORD environment variable
    env = {"PGPASSWORD": password}

    try:
        # Execute pg_dump
        result = subprocess.run(
            pg_dump_cmd,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )

        dump_data = result.stdout

        # Archive the dump
        archive_id = f"pgdump-{table_name}-{uuid.uuid4().hex}"
        metadata = archive_service.archive_data(
            archive_id=archive_id,
            data_type=DataType.AUDIT_LOG,  # Use audit log as generic type
            data={"dump": dump_data, "table": table_name},
            metadata={
                "table_name": table_name,
                "where_clause": where_clause,
                "dump_size_bytes": len(dump_data),
            },
        )

        return {
            "status": (
                "success" if metadata.status == ArchiveStatus.COMPLETED else "failed"
            ),
            "archive_id": archive_id,
            "table_name": table_name,
            "s3_key": metadata.file_path,
            "dump_size": len(dump_data),
            "checksum": metadata.checksum,
        }

    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "message": f"pg_dump failed: {e.stderr}",
            "table_name": table_name,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "table_name": table_name,
        }


@shared_task(bind=True, max_retries=3)
def restore_from_archive_task(
    self,
    archive_id: str,
    s3_key: str,
    target_table: str | None = None,
) -> dict[str, Any]:
    """
    Restore data from archive to database.

    Args:
        archive_id: Archive identifier
        s3_key: S3 object key
        target_table: Target table for restore (for pg_dump restores)

    Returns:
        Task result with restore details
    """
    archive_service = ArchiveService()

    try:
        # Restore archive data
        data = archive_service.restore_archive(archive_id, s3_key)

        # If this is a pg_dump, restore to database
        if target_table and isinstance(data, dict) and "dump" in data:
            settings = get_settings()
            db_url = settings.database_url

            if not db_url or "postgresql" not in db_url:
                return {
                    "status": "error",
                    "message": "PostgreSQL database required for restore",
                }

            # Parse connection parameters (same as pg_dump)
            url_parts = db_url.replace("postgresql+asyncpg://", "").split("@")
            user_pass = url_parts[0].split(":")
            host_db = url_parts[1].split("/")
            host_port = host_db[0].split(":")

            user = user_pass[0]
            password = user_pass[1] if len(user_pass) > 1 else ""
            host = host_port[0]
            port = host_port[1] if len(host_port) > 1 else "5432"
            database = host_db[0]

            # Build psql command
            psql_cmd = [
                "psql",
                f"--host={host}",
                f"--port={port}",
                f"--username={user}",
                f"--dbname={database}",
            ]

            env = {"PGPASSWORD": password}

            try:
                subprocess.run(
                    psql_cmd,
                    input=data["dump"],
                    capture_output=True,
                    text=True,
                    env=env,
                    check=True,
                )

                return {
                    "status": "success",
                    "archive_id": archive_id,
                    "target_table": target_table,
                    "restored_at": datetime.now(UTC).isoformat(),
                }
            except subprocess.CalledProcessError as e:
                return {
                    "status": "error",
                    "message": f"psql restore failed: {e.stderr}",
                    "archive_id": archive_id,
                }

        return {
            "status": "success",
            "archive_id": archive_id,
            "restored_at": datetime.now(UTC).isoformat(),
            "data_type": type(data).__name__,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "archive_id": archive_id,
        }


@shared_task
def cleanup_old_archives_task(retention_days: int = 90) -> dict[str, Any]:
    """
    Clean up archives older than specified retention period.

    Args:
        retention_days: Number of days to keep archives

    Returns:
        Task result with cleanup details
    """
    archive_service = ArchiveService()
    RetentionService()

    cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)

    # List all archives
    archives = archive_service.list_archives()

    deleted_count = 0
    failed_count = 0

    for archive in archives:
        last_modified = archive["last_modified"]
        if last_modified < cutoff_date:
            try:
                archive_service.delete_archive(archive["key"])
                deleted_count += 1
            except Exception:
                failed_count += 1

    return {
        "status": "success",
        "total_archives": len(archives),
        "deleted_count": deleted_count,
        "failed_count": failed_count,
        "cutoff_date": cutoff_date.isoformat(),
    }
