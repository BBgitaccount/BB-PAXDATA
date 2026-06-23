"""Audit Log API endpoints with hash chain verification."""

import io
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.services.gdpr_compliance_service import (
    GDPRComplianceService,
)
from bb_paxdata.infrastructure.db.repositories.audit_log_repository import (
    AuditLogRepository,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter(
    prefix="/audit-log",
    tags=["Audit Log"],
)


def get_audit_log_repository(db: AsyncSession = Depends(get_db)):
    """Dependency injection for AuditLogRepository."""
    return AuditLogRepository(db)


class AuditLogEntrySchema(BaseModel):
    """Schema for audit log entry response."""

    id: str
    timestamp: datetime
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    before_state: dict | None = None
    after_state: dict | None = None
    correlation_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    hash_chain: str | None = None

    class Config:
        from_attributes = True


class AuditLogVerificationSchema(BaseModel):
    """Schema for audit log verification result."""

    is_valid: bool
    total_entries: int
    verified_entries: int
    first_violation_index: int | None = None
    first_violation_details: str | None = None
    violations: list[dict] = []


@router.get("/verify")
async def verify_audit_chain(
    start_date: Annotated[datetime | None, Query(None)] = None,
    end_date: Annotated[datetime | None, Query(None)] = None,
    repo=Depends(get_audit_log_repository),
):
    """
    Verify the integrity of the audit log hash chain.

    Checks that each entry's hash_chain field matches the computed hash
    of the previous entry in chronological order.

    Query parameters:
    - start_date: Optional start date for verification range
    - end_date: Optional end date for verification range
    """
    result = await repo.verify_chain_integrity(start_date=start_date, end_date=end_date)
    return AuditLogVerificationSchema(
        is_valid=result.is_valid,
        total_entries=result.total_entries,
        verified_entries=result.verified_entries,
        first_violation_index=result.first_violation_index,
        first_violation_details=result.first_violation_details,
        violations=result.violations,
    )


@router.get("/search")
async def search_audit_log(
    actor_id: Annotated[str | None, Query(None)] = None,
    action: Annotated[str | None, Query(None)] = None,
    resource_type: Annotated[str | None, Query(None)] = None,
    resource_id: Annotated[str | None, Query(None)] = None,
    start_date: Annotated[datetime | None, Query(None)] = None,
    end_date: Annotated[datetime | None, Query(None)] = None,
    limit: Annotated[int, Query(100, ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(0, ge=0)] = 0,
    repo=Depends(get_audit_log_repository),
):
    """
    Search audit log entries with filters.

    Query parameters:
    - actor_id: Filter by actor ID
    - action: Filter by action type
    - resource_type: Filter by resource type
    - resource_id: Filter by resource ID
    - start_date: Filter by start date
    - end_date: Filter by end date
    - limit: Maximum number of results (default: 100, max: 1000)
    - offset: Pagination offset (default: 0)
    """
    entries = await repo.search(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return [AuditLogEntrySchema.model_validate(entry) for entry in entries]


@router.get("/correlation/{correlation_id}")
async def get_audit_by_correlation(
    correlation_id: str,
    repo=Depends(get_audit_log_repository),
):
    """Retrieve all audit log entries for a given correlation ID."""
    entries = await repo.get_by_correlation_id(correlation_id)
    return [AuditLogEntrySchema.model_validate(entry) for entry in entries]


@router.get("/{entry_id}")
async def get_audit_entry(
    entry_id: str,
    repo=Depends(get_audit_log_repository),
):
    """Retrieve a single audit log entry by ID."""
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Audit log entry not found: {entry_id}",
        )

    return AuditLogEntrySchema.model_validate(entry)


@router.get("/export/csv")
async def export_audit_csv(
    actor_id: Annotated[str | None, Query(None)] = None,
    action: Annotated[str | None, Query(None)] = None,
    resource_type: Annotated[str | None, Query(None)] = None,
    resource_id: Annotated[str | None, Query(None)] = None,
    start_date: Annotated[datetime | None, Query(None)] = None,
    end_date: Annotated[datetime | None, Query(None)] = None,
    repo=Depends(get_audit_log_repository),
):
    """Export audit log entries as CSV file."""
    import csv
    import io

    entries = await repo.search(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        limit=10000,  # Higher limit for exports
        offset=0,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "id",
            "timestamp",
            "actor_id",
            "action",
            "resource_type",
            "resource_id",
            "correlation_id",
            "ip_address",
            "user_agent",
            "hash_chain",
        ]
    )

    # Rows
    for entry in entries:
        writer.writerow(
            [
                entry.id,
                entry.timestamp.isoformat(),
                entry.actor_id,
                entry.action,
                entry.resource_type,
                entry.resource_id,
                entry.correlation_id or "",
                entry.ip_address or "",
                entry.user_agent or "",
                entry.hash_chain or "",
            ]
        )

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )


@router.get("/export/json")
async def export_audit_json(
    actor_id: Annotated[str | None, Query(None)] = None,
    action: Annotated[str | None, Query(None)] = None,
    resource_type: Annotated[str | None, Query(None)] = None,
    resource_id: Annotated[str | None, Query(None)] = None,
    start_date: Annotated[datetime | None, Query(None)] = None,
    end_date: Annotated[datetime | None, Query(None)] = None,
    repo=Depends(get_audit_log_repository),
):
    """Export audit log entries as JSON file."""
    import json

    entries = await repo.search(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        limit=10000,
        offset=0,
    )

    data = [entry.model_dump() for entry in entries]
    json_str = json.dumps(data, indent=2, default=str)

    return StreamingResponse(
        io.BytesIO(json_str.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_log.json"},
    )


@router.get("/export/pdf")
async def export_audit_pdf(
    actor_id: Annotated[str | None, Query(None)] = None,
    action: Annotated[str | None, Query(None)] = None,
    resource_type: Annotated[str | None, Query(None)] = None,
    resource_id: Annotated[str | None, Query(None)] = None,
    start_date: Annotated[datetime | None, Query(None)] = None,
    end_date: Annotated[datetime | None, Query(None)] = None,
    repo=Depends(get_audit_log_repository),
):
    """Export audit log entries as PDF file."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

        entries = await repo.search(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000,  # Lower limit for PDF
            offset=0,
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)

        elements = []

        # Title
        styles = getSampleStyleSheet()
        title = Paragraph("Audit Log Export", styles["Title"])
        elements.append(title)

        # Table data
        table_data = [
            [
                "Timestamp",
                "Actor",
                "Action",
                "Resource Type",
                "Resource ID",
                "Correlation ID",
            ],
        ]

        for entry in entries:
            table_data.append(
                [
                    entry.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    entry.actor_id[:20],
                    entry.action,
                    entry.resource_type[:15],
                    entry.resource_id[:20],
                    entry.correlation_id[:20] if entry.correlation_id else "",
                ]
            )

        # Create table
        table = Table(
            table_data,
            colWidths=[
                1.5 * inch,
                1 * inch,
                1 * inch,
                1.2 * inch,
                1.5 * inch,
                1.5 * inch,
            ],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), "#CCCCCC"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), "BLACK"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), "#EEEEEE"),
                    ("GRID", (0, 0), (-1, -1), 1, "BLACK"),
                ]
            )
        )

        elements.append(table)

        doc.build(elements)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=audit_log.pdf"},
        )

    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PDF export requires reportlab library. Install with: pip install reportlab",
        )


@router.get("/compliance/gdpr-article-30")
async def gdpr_article_30_report(
    start_date: Annotated[datetime | None, Query(None)] = None,
    end_date: Annotated[datetime | None, Query(None)] = None,
    repo=Depends(get_audit_log_repository),
):
    """
    Generate GDPR Article 30 compliance report.

    Article 30 requires records of processing activities including:
    - Purposes of processing
    - Categories of data subjects and personal data
    - Categories of recipients
    - Retention periods
    - Security measures

    Query parameters:
    - start_date: Optional start date for report range
    - end_date: Optional end date for report range
    """
    entries = await repo.search(
        start_date=start_date,
        end_date=end_date,
        limit=10000,
        offset=0,
    )

    report = GDPRComplianceService.generate_article_30_report(
        entries=entries,
        report_date=datetime.utcnow(),
    )

    return report
