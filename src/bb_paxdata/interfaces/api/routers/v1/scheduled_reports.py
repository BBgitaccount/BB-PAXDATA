# src/bb_paxdata/interfaces/api/routers/v1/scheduled_reports.py
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.scheduled_reports_table import (
    ReportEmbedToken,
    ScheduledReport,
)
from bb_paxdata.infrastructure.scheduled_reports.consent_manager import ConsentManager
from bb_paxdata.infrastructure.scheduled_reports.embed_token import (
    EmbedTokenManager,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter()
consent_manager = ConsentManager()
embed_manager = EmbedTokenManager()


# Request/Response Schemas
class ScheduledReportCreateRequest(BaseModel):
    name: str = Field(..., description="Report name")
    template_id: str | None = Field(None, description="Template ID to use")
    session_filter: dict | None = Field(None, description="Session filter criteria")
    frequency: str = Field(
        ..., description="Frequency: daily, weekly, monthly, quarterly"
    )
    day_of_week: int | None = Field(None, description="Day of week (0-6) for weekly")
    day_of_month: int | None = Field(
        None, description="Day of month (1-28) for monthly"
    )
    time_of_day: str = Field("06:00:00", description="Time of day HH:MM:SS")
    timezone: str = Field("Europe/Istanbul", description="Timezone")
    export_formats: list[str] = Field(default=["pdf"], description="Export formats")


class ScheduledReportResponse(BaseModel):
    id: str
    name: str
    template_id: str | None
    frequency: str
    is_active: bool
    last_run_at: str | None
    next_run_at: str | None
    created_at: str


class RecipientCreateRequest(BaseModel):
    email: str = Field(..., description="Recipient email")
    name: str | None = Field(None, description="Recipient name")


class EmbedTokenCreateRequest(BaseModel):
    name: str = Field(..., description="Token name")
    allowed_origins: list[str] = Field(..., description="Allowed origins")
    expires_in_days: int | None = Field(None, description="Expiration in days")


@router.post(
    "/", response_model=ScheduledReportResponse, status_code=status.HTTP_201_CREATED
)
async def create_scheduled_report(
    report_req: ScheduledReportCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ScheduledReportResponse:
    """Create a new scheduled report."""
    report_id = str(uuid.uuid4())

    report = ScheduledReport(
        id=report_id,
        name=report_req.name,
        template_id=report_req.template_id,
        session_filter=(
            json.dumps(report_req.session_filter) if report_req.session_filter else None
        ),
        frequency=report_req.frequency,
        day_of_week=report_req.day_of_week,
        day_of_month=report_req.day_of_month,
        time_of_day=report_req.time_of_day,
        timezone=report_req.timezone,
        export_formats=json.dumps(report_req.export_formats),
        is_active=True,
        created_by=None,  # Would come from auth
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return ScheduledReportResponse(
        id=report.id,
        name=report.name,
        template_id=report.template_id,
        frequency=report.frequency,
        is_active=report.is_active,
        last_run_at=report.last_run_at.isoformat() if report.last_run_at else None,
        next_run_at=report.next_run_at.isoformat() if report.next_run_at else None,
        created_at=report.created_at.isoformat() if report.created_at else "",
    )


@router.get("/", response_model=list[ScheduledReportResponse])
async def list_scheduled_reports(
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[ScheduledReportResponse]:
    """List scheduled reports."""
    stmt = select(ScheduledReport)
    if is_active is not None:
        stmt = stmt.where(ScheduledReport.is_active == is_active)

    stmt = stmt.order_by(ScheduledReport.created_at.desc())
    result = await db.scalars(stmt)
    reports = result.all()

    return [
        ScheduledReportResponse(
            id=r.id,
            name=r.name,
            template_id=r.template_id,
            frequency=r.frequency,
            is_active=r.is_active,
            last_run_at=r.last_run_at.isoformat() if r.last_run_at else None,
            next_run_at=r.next_run_at.isoformat() if r.next_run_at else None,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in reports
    ]


@router.get("/{report_id}", response_model=ScheduledReportResponse)
async def get_scheduled_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
) -> ScheduledReportResponse:
    """Get a single scheduled report."""
    stmt = select(ScheduledReport).where(ScheduledReport.id == report_id)
    report = await db.scalar(stmt)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled report not found: {report_id}",
        )

    return ScheduledReportResponse(
        id=report.id,
        name=report.name,
        template_id=report.template_id,
        frequency=report.frequency,
        is_active=report.is_active,
        last_run_at=report.last_run_at.isoformat() if report.last_run_at else None,
        next_run_at=report.next_run_at.isoformat() if report.next_run_at else None,
        created_at=report.created_at.isoformat() if report.created_at else "",
    )


@router.put("/{report_id}", response_model=ScheduledReportResponse)
async def update_scheduled_report(
    report_id: str,
    report_req: ScheduledReportCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ScheduledReportResponse:
    """Update a scheduled report."""
    stmt = select(ScheduledReport).where(ScheduledReport.id == report_id)
    report = await db.scalar(stmt)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled report not found: {report_id}",
        )

    update_data = {
        "name": report_req.name,
        "template_id": report_req.template_id,
        "session_filter": (
            json.dumps(report_req.session_filter) if report_req.session_filter else None
        ),
        "frequency": report_req.frequency,
        "day_of_week": report_req.day_of_week,
        "day_of_month": report_req.day_of_month,
        "time_of_day": report_req.time_of_day,
        "timezone": report_req.timezone,
        "export_formats": json.dumps(report_req.export_formats),
    }

    await db.execute(
        update(ScheduledReport)
        .where(ScheduledReport.id == report_id)
        .values(**update_data)
    )
    await db.commit()
    await db.refresh(report)

    return ScheduledReportResponse(
        id=report.id,
        name=report.name,
        template_id=report.template_id,
        frequency=report.frequency,
        is_active=report.is_active,
        last_run_at=report.last_run_at.isoformat() if report.last_run_at else None,
        next_run_at=report.next_run_at.isoformat() if report.next_run_at else None,
        created_at=report.created_at.isoformat() if report.created_at else "",
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a scheduled report."""
    stmt = select(ScheduledReport).where(ScheduledReport.id == report_id)
    report = await db.scalar(stmt)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled report not found: {report_id}",
        )

    await db.delete(report)
    await db.commit()


@router.post("/{report_id}/recipients")
async def add_recipient(
    report_id: str,
    recipient_req: RecipientCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a recipient to the distribution list (requires consent)."""
    # Verify report exists
    stmt = select(ScheduledReport).where(ScheduledReport.id == report_id)
    report = await db.scalar(stmt)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled report not found: {report_id}",
        )

    token = await consent_manager.add_recipient_with_consent(
        scheduled_report_id=report_id,
        email=recipient_req.email,
        name=recipient_req.name,
        added_by=None,  # Would come from auth
    )

    return {
        "message": "Recipient added. Consent email sent.",
        "consent_token": token,
    }


@router.get("/consent/{token}")
async def confirm_consent(token: str) -> dict:
    """Confirm consent via email link."""
    try:
        await consent_manager.confirm_consent(token)
        return {"message": "Consent confirmed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/unsubscribe/{token}")
async def unsubscribe(token: str) -> dict:
    """Unsubscribe via email link."""
    success = await consent_manager.unsubscribe(token)
    if success:
        return {"message": "Successfully unsubscribed"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid unsubscribe token"
        )


@router.post("/{report_id}/embed-tokens")
async def create_embed_token(
    report_id: str,
    token_req: EmbedTokenCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create an embed token for iframe access."""
    # Verify report exists
    stmt = select(ScheduledReport).where(ScheduledReport.id == report_id)
    report = await db.scalar(stmt)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled report not found: {report_id}",
        )

    # Generate JWT token
    jwt_token = embed_manager.create_embed_token(
        scheduled_report_id=report_id,
        name=token_req.name,
        allowed_origins=token_req.allowed_origins,
        expires_in_days=token_req.expires_in_days,
    )

    # Store in database
    embed_token = ReportEmbedToken(
        scheduled_report_id=report_id,
        token=jwt_token,
        name=token_req.name,
        allowed_origins=json.dumps(token_req.allowed_origins),
        expires_at=(
            datetime.now(UTC).replace(tzinfo=None)
            + timedelta(days=token_req.expires_in_days)
            if token_req.expires_in_days
            else None
        ),
        created_by=None,
    )
    db.add(embed_token)
    await db.commit()

    return {
        "token": jwt_token,
        "embed_url": f"/api/v1/scheduled-reports/embed/{jwt_token}",
        "expires_at": (
            embed_token.expires_at.isoformat() if embed_token.expires_at else None
        ),
    }


@router.get("/embed/{token}")
async def get_embed_content(
    token: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Get embed content for iframe (public endpoint with JWT validation)."""
    # Verify token
    origin = request.headers.get("origin", "")
    try:
        payload = embed_manager.verify_embed_token(token, origin)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # Set CSP headers
    allowed_origins = payload.get("origins", [])
    if allowed_origins:
        csp = f"frame-ancestors {' '.join(allowed_origins)}"
        response.headers["Content-Security-Policy"] = csp

    # Get latest report data
    report_id = payload["sub"]
    stmt = select(ScheduledReport).where(ScheduledReport.id == report_id)
    report = await db.scalar(stmt)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    # Return embed HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{report.name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            .header {{ border-bottom: 2px solid #1F3864; padding-bottom: 10px; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{report.name}</h1>
            <p>Embedded Report View</p>
        </div>
        <div id="report-content">
            <p>Report content would be rendered here based on template: {report.template_id}</p>
        </div>
    </body>
    </html>
    """

    return Response(content=html, media_type="text/html")
