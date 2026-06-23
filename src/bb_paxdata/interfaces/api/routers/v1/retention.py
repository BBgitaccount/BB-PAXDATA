"""
API router for data retention and archiving (TASK-1.3)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from bb_paxdata.application.domain.models.retention import DataType
from bb_paxdata.application.domain.services.pii_anonymization_service import (
    GDPRRightToBeForgottenService,
    PIIAnonymizationService,
)
from bb_paxdata.application.domain.services.retention_service import (
    ArchiveService,
    RetentionService,
)
from bb_paxdata.infrastructure.tasks.retention_tasks import (
    archive_expired_data_task,
    cleanup_old_archives_task,
    delete_expired_data_task,
    pg_dump_and_archive_task,
    restore_from_archive_task,
)

router = APIRouter(prefix="/retention", tags=["retention"])


# ── Schemas ─────────────────────────────────────────────────────────────


class RetentionPolicyResponse(BaseModel):
    """Response for retention policy query."""

    data_type: str
    retention_years: int
    permanent: bool
    archive_before_deletion: bool


class ArchiveRequest(BaseModel):
    """Request to archive data."""

    data_type: str = Field(..., description="Type of data to archive")
    record_ids: list[str] = Field(
        default_factory=list, description="Record IDs to archive"
    )


class ArchiveResponse(BaseModel):
    """Response for archive operation."""

    archive_id: str
    status: str
    data_type: str
    s3_key: str | None = None
    checksum: str | None = None
    file_size: int | None = None
    error: str | None = None


class RestoreRequest(BaseModel):
    """Request to restore archived data."""

    archive_id: str
    s3_key: str
    target_table: str | None = None


class RestoreResponse(BaseModel):
    """Response for restore operation."""

    archive_id: str
    status: str
    restored_at: str | None = None
    error: str | None = None


class PIIAnonymizeRequest(BaseModel):
    """Request to anonymize text."""

    text: str
    speaker_id: str | None = None
    location: str | None = None
    language: str = "en"


class PIIAnonymizeResponse(BaseModel):
    """Response for PII anonymization."""

    original_text: str
    masked_text: str
    detected_entities: list[dict[str, Any]]
    speaker_mapping: dict[str, str]
    location_mapping: dict[str, str]
    timestamp: str


class GDPRDeletionRequest(BaseModel):
    """Request for GDPR data deletion."""

    user_id: str
    reason: str | None = None


class GDPRDeletionResponse(BaseModel):
    """Response for GDPR deletion request."""

    request_id: str
    user_id: str
    status: str
    created_at: str
    estimated_completion: str


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get("/policy/{data_type}", response_model=RetentionPolicyResponse)
async def get_retention_policy(data_type: str) -> RetentionPolicyResponse:
    """
    Get retention policy for a specific data type.

    Args:
        data_type: Type of data (raw_transcript, ai_analysis, etc.)

    Returns:
        Retention policy details
    """
    try:
        data_type_enum = DataType(data_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data type: {data_type}",
        )

    service = RetentionService()
    policy = service.get_policy(data_type_enum)

    return RetentionPolicyResponse(
        data_type=policy.data_type.value,
        retention_years=policy.retention_years,
        permanent=policy.permanent,
        archive_before_deletion=policy.archive_before_deletion,
    )


@router.post("/archive", response_model=ArchiveResponse)
async def archive_data(request: ArchiveRequest) -> ArchiveResponse:
    """
    Archive expired data of a specific type.

    This triggers an async Celery task to perform the archiving.
    """
    try:
        DataType(request.data_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data type: {request.data_type}",
        )

    # Trigger async task
    task = archive_expired_data_task.delay(request.data_type)

    return ArchiveResponse(
        archive_id=task.id,
        status="pending",
        data_type=request.data_type,
    )


@router.post("/archive/pgdump", response_model=ArchiveResponse)
async def pg_dump_archive(
    table_name: str,
    where_clause: str | None = None,
) -> ArchiveResponse:
    """
    Perform pg_dump for a specific table and archive to S3/MinIO.

    Args:
        table_name: Database table to dump
        where_clause: Optional WHERE clause to filter records

    Returns:
        Archive operation result
    """
    # Trigger async task
    task = pg_dump_and_archive_task.delay(table_name, where_clause)

    return ArchiveResponse(
        archive_id=task.id,
        status="pending",
        data_type="pgdump",
    )


@router.post("/restore", response_model=RestoreResponse)
async def restore_archive(request: RestoreRequest) -> RestoreResponse:
    """
    Restore data from archive.

    This triggers an async Celery task to perform the restore.
    """
    # Trigger async task
    restore_from_archive_task.delay(
        request.archive_id, request.s3_key, request.target_table
    )

    return RestoreResponse(
        archive_id=request.archive_id,
        status="pending",
    )


@router.post("/delete-expired")
async def delete_expired_data(data_type: str, archive_id: str) -> dict[str, Any]:
    """
    Delete expired data from database after successful archiving.

    This triggers an async Celery task to perform the deletion.
    """
    try:
        DataType(data_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data type: {data_type}",
        )

    # Trigger async task
    task = delete_expired_data_task.delay(data_type, archive_id)

    return {
        "task_id": task.id,
        "status": "pending",
        "data_type": data_type,
        "archive_id": archive_id,
    }


@router.post("/cleanup-archives")
async def cleanup_archives(retention_days: int = 90) -> dict[str, Any]:
    """
    Clean up archives older than specified retention period.

    Args:
        retention_days: Number of days to keep archives

    Returns:
        Cleanup operation result
    """
    # Trigger async task
    task = cleanup_old_archives_task.delay(retention_days)

    return {
        "task_id": task.id,
        "status": "pending",
        "retention_days": retention_days,
    }


@router.post("/pii/anonymize", response_model=PIIAnonymizeResponse)
async def anonymize_pii(request: PIIAnonymizeRequest) -> PIIAnonymizeResponse:
    """
    Anonymize PII in text.

    Detects and masks personally identifiable information including:
    - Speaker names (encoded as P-001, P-002, etc.)
    - Location information (generalized)
    - Email addresses
    - Phone numbers
    """
    service = PIIAnonymizationService()
    result = service.anonymize_text(
        text=request.text,
        speaker_id=request.speaker_id,
        location=request.location,
        language=request.language,
    )

    return PIIAnonymizeResponse(
        original_text=result.original_text,
        masked_text=result.masked_text,
        detected_entities=result.detected_entities,
        speaker_mapping=result.speaker_mapping,
        location_mapping=result.location_mapping,
        timestamp=result.timestamp.isoformat(),
    )


@router.post("/gdpr/deletion-request", response_model=GDPRDeletionResponse)
async def request_gdpr_deletion(request: GDPRDeletionRequest) -> GDPRDeletionResponse:
    """
    Submit a GDPR Right to be Forgotten deletion request.

    This initiates the process to anonymize/delete all data related to a user.
    """
    service = GDPRRightToBeForgottenService()
    result = service.request_data_deletion(
        user_id=request.user_id,
        reason=request.reason,
    )

    return GDPRDeletionResponse(
        request_id=result["request_id"],
        user_id=result["user_id"],
        status=result["status"],
        created_at=result["created_at"],
        estimated_completion=result["estimated_completion"],
    )


@router.get("/gdpr/verify/{request_id}")
async def verify_gdpr_deletion(request_id: str) -> dict[str, Any]:
    """
    Verify that a GDPR deletion request has been completed.

    Args:
        request_id: Deletion request identifier

    Returns:
        Verification status
    """
    service = GDPRRightToBeForgottenService()
    result = service.verify_deletion_complete(request_id)

    return result


@router.get("/archives")
async def list_archives(data_type: str | None = None) -> list[dict[str, Any]]:
    """
    List available archives.

    Args:
        data_type: Optional filter by data type

    Returns:
        List of archive metadata
    """
    service = ArchiveService()

    data_type_enum = DataType(data_type) if data_type else None
    archives = service.list_archives(data_type_enum)

    return archives


@router.delete("/archives/{s3_key}")
async def delete_archive(s3_key: str) -> dict[str, Any]:
    """
    Delete an archive from S3/MinIO.

    Args:
        s3_key: S3 object key

    Returns:
        Deletion result
    """
    service = ArchiveService()

    try:
        service.delete_archive(s3_key)
        return {"status": "success", "s3_key": s3_key}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
