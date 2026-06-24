"""Drift Monitoring API Router.

Provides endpoints for drift detection monitoring, alerts, and reports.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.monitoring.services.drift_metrics_service import (
    DriftScore,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter(prefix="/monitoring/drift", tags=["monitoring"])


class DriftAlert(BaseModel):
    """Drift alert model."""

    id: str
    alert_type: str
    field: str
    severity: str
    detected_at: datetime
    resolved: bool = False
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = {}


class WeeklyDriftReport(BaseModel):
    """Weekly drift report model."""

    report_period: str
    generated_at: datetime
    summary: dict[str, Any]
    field_details: dict[str, dict[str, Any]]


@router.get("/summary")
async def get_drift_summary(
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, str]]:
    """Get latest drift severity per field for the past 30 days.

    Returns:
        Dictionary mapping field names to their latest severity
    """
    try:
        # Query latest severity per field from drift_measurements table
        # For now, return placeholder data
        return {
            "fields": {
                "sentiment_score": "stable",
                "risk_score": "warning",
                "ai_confidence": "stable",
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get drift summary: {e!s}",
        )


@router.get("/timeseries")
async def get_drift_timeseries(
    field: str = Query(..., description="Field name to query"),
    metric: str = Query(..., description="Metric type (PSI, KL, KS, Wasserstein)"),
    days: int = Query(default=30, ge=1, le=365, description="Number of days to query"),
    db: AsyncSession = Depends(get_db),
) -> list[DriftScore]:
    """Get chronological drift scores for a field and metric.

    Args:
        field: Field name to query
        metric: Metric type (PSI, KL, KS, Wasserstein)
        days: Number of days to query (default: 30)
        db: Database session

    Returns:
        List of DriftScore objects in chronological order
    """
    try:
        # Query drift_measurements table for given field and metric
        # For now, return placeholder data
        end_date = datetime.now(timezone.utc)
        end_date - timedelta(days=days)

        # Placeholder - would query actual database
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get drift timeseries: {e!s}",
        )


@router.get("/alerts")
async def get_drift_alerts(
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    db: AsyncSession = Depends(get_db),
) -> list[DriftAlert]:
    """Get drift alerts filtered by resolved status.

    Args:
        resolved: Filter by resolved status (None = all alerts)
        db: Database session

    Returns:
        List of drift alerts
    """
    try:
        # Query drift_alerts table with optional filter
        # For now, return placeholder data
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get drift alerts: {e!s}",
        )


@router.post("/alerts/{alert_id}/resolve")
async def resolve_drift_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
) -> DriftAlert:
    """Resolve a drift alert (admin role required).

    Args:
        alert_id: ID of the alert to resolve
        db: Database session

    Returns:
        Updated drift alert
    """
    try:
        # Update drift_alerts table: set resolved=true, resolved_at=NOW()
        # For now, return placeholder
        return DriftAlert(
            id=alert_id,
            alert_type="prediction_drift",
            field="risk_score",
            severity="warning",
            detected_at=datetime.now(timezone.utc),
            resolved=True,
            resolved_at=datetime.now(timezone.utc),
            metadata={},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve drift alert: {e!s}",
        )


@router.get("/report")
async def get_weekly_drift_report(
    db: AsyncSession = Depends(get_db),
) -> WeeklyDriftReport:
    """Get the latest weekly drift report.

    Returns:
        Latest WeeklyDriftReport from drift_reports table
    """
    try:
        # Query latest row from drift_reports table
        # For now, return placeholder data
        return WeeklyDriftReport(
            report_period="2025-W22",
            generated_at=datetime.now(timezone.utc),
            summary={
                "total_alerts": 3,
                "critical": 1,
                "warning": 2,
                "stable_fields": ["discourse_act", "frame"],
            },
            field_details={
                "sentiment_score": {
                    "psi": 0.23,
                    "severity": "critical",
                    "trend": "increasing",
                    "recommendation": "concept_drift_detected_retrain_suggested",
                }
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get weekly drift report: {e!s}",
        )
