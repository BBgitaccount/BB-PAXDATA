# src/bb_paxdata/interfaces/api/routers/v1/exports.py
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.export_job_table import (
    ExportJob,
    ExportStatus,
    ExportType,
)
from bb_paxdata.infrastructure.db.models import File
from bb_paxdata.infrastructure.tasks.celery_app import get_celery_app
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
celery_app = get_celery_app()


# Request/Response Schemas
class PDFExportRequest(BaseModel):
    file_id: str = Field(..., description="File ID to export")
    template_id: str | None = Field(None, description="Template ID (null = default)")
    language: str = Field("en", description="Language: tr | en | fr | ar")
    include_sections: list[str] = Field(
        default=["title", "abstract", "analysis", "risks"],
        description="Sections to include",
    )
    chart_dpi: int = Field(150, description="Chart DPI")
    anonymize_speakers: bool = Field(False, description="Anonymize speaker names")


class ExcelExportRequest(BaseModel):
    file_id: str = Field(..., description="File ID to export")
    include_sheets: list[str] = Field(
        default=["summary", "statements", "risks"], description="Sheets to include"
    )
    language: str = Field("en", description="Language: tr | en")
    max_rows_per_sheet: int = Field(50000, description="Max rows per sheet")
    anonymize_speakers: bool = Field(False, description="Anonymize speaker names")
    date_range: dict | None = Field(None, description="Date range filter")


class GEXFExportRequest(BaseModel):
    file_id: str = Field(..., description="File ID to export")
    mode: str = Field("static", description="Mode: static | dynamic")
    time_interval: str = Field(
        "session", description="Time interval: session | daily | hourly"
    )
    include_centrality: bool = Field(True, description="Include centrality metrics")
    min_edge_weight: float = Field(1.0, description="Minimum edge weight")
    time_range: dict | None = Field(None, description="Time range filter")
    anonymize_speakers: bool = Field(False, description="Anonymize speaker names")


class ExportResponse(BaseModel):
    job_id: str
    status: str
    estimated_seconds: int = 45
    poll_url: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_pct: int
    download_url: str | None = None
    expires_at: str | None = None
    error: str | None = None


@router.post(
    "/pdf", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit("10/hour")
async def create_pdf_export(
    request: Request,
    export_req: PDFExportRequest,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """Create a PDF export job."""
    # Verify file exists
    stmt = select(File).where(File.file_id == export_req.file_id)
    file_obj = await db.scalar(stmt)
    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {export_req.file_id}",
        )

    # Create export job
    job_id = str(uuid.uuid4())
    job = ExportJob(
        id=job_id,
        user_id=request.headers.get("X-User-ID"),
        file_id=export_req.file_id,
        export_type=ExportType.PDF.value,
        status=ExportStatus.QUEUED.value,
        progress_pct=0,
        options=json.dumps(export_req.model_dump()),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(job)
    await db.commit()

    # Queue Celery task
    celery_app.send_task(
        "export.pdf",
        args=[job_id, export_req.file_id, export_req.model_dump()],
    )

    return ExportResponse(
        job_id=job_id,
        status=ExportStatus.QUEUED.value,
        estimated_seconds=45,
        poll_url=f"/api/v1/exports/jobs/{job_id}",
    )


@router.post(
    "/excel", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit("10/hour")
async def create_excel_export(
    request: Request,
    export_req: ExcelExportRequest,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """Create an Excel export job."""
    # Verify file exists
    stmt = select(File).where(File.file_id == export_req.file_id)
    file_obj = await db.scalar(stmt)
    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {export_req.file_id}",
        )

    # Create export job
    job_id = str(uuid.uuid4())
    job = ExportJob(
        id=job_id,
        user_id=request.headers.get("X-User-ID"),
        file_id=export_req.file_id,
        export_type=ExportType.EXCEL.value,
        status=ExportStatus.QUEUED.value,
        progress_pct=0,
        options=json.dumps(export_req.model_dump()),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(job)
    await db.commit()

    # Queue Celery task
    celery_app.send_task(
        "export.excel",
        args=[job_id, export_req.file_id, export_req.model_dump()],
    )

    return ExportResponse(
        job_id=job_id,
        status=ExportStatus.QUEUED.value,
        estimated_seconds=30,
        poll_url=f"/api/v1/exports/jobs/{job_id}",
    )


@router.post(
    "/gexf", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit("10/hour")
async def create_gexf_export(
    request: Request,
    export_req: GEXFExportRequest,
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """Create a GEXF network export job."""
    # Verify file exists
    stmt = select(File).where(File.file_id == export_req.file_id)
    file_obj = await db.scalar(stmt)
    if not file_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {export_req.file_id}",
        )

    # Create export job
    job_id = str(uuid.uuid4())
    job = ExportJob(
        id=job_id,
        user_id=request.headers.get("X-User-ID"),
        file_id=export_req.file_id,
        export_type=ExportType.GEXF.value,
        status=ExportStatus.QUEUED.value,
        progress_pct=0,
        options=json.dumps(export_req.model_dump()),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(job)
    await db.commit()

    # Queue Celery task
    celery_app.send_task(
        "export.gexf",
        args=[job_id, export_req.file_id, export_req.model_dump()],
    )

    return ExportResponse(
        job_id=job_id,
        status=ExportStatus.QUEUED.value,
        estimated_seconds=15,
        poll_url=f"/api/v1/exports/jobs/{job_id}",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """Get the status of an export job."""
    stmt = select(ExportJob).where(ExportJob.id == job_id)
    job = await db.scalar(stmt)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job not found: {job_id}",
        )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress_pct=job.progress_pct,
        download_url=job.download_url,
        expires_at=job.expires_at.isoformat() if job.expires_at else None,
        error=job.error_message,
    )


@router.get("/jobs")
async def list_jobs(
    file_id: str | None = None,
    export_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List export jobs with optional filters."""
    stmt = select(ExportJob)

    if file_id:
        stmt = stmt.where(ExportJob.file_id == file_id)
    if export_type:
        stmt = stmt.where(ExportJob.export_type == export_type)
    if status:
        stmt = stmt.where(ExportJob.status == status)

    stmt = stmt.order_by(ExportJob.created_at.desc()).limit(limit).offset(offset)

    result = await db.scalars(stmt)
    jobs = result.all()

    return {
        "jobs": [
            {
                "job_id": job.id,
                "file_id": job.file_id,
                "export_type": job.export_type,
                "status": job.status,
                "progress_pct": job.progress_pct,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": (
                    job.completed_at.isoformat() if job.completed_at else None
                ),
            }
            for job in jobs
        ],
        "total": len(jobs),
    }
