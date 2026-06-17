import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.config.settings import get_settings
from bb_paxdata.interfaces.api.dependencies import PermissionChecker, get_db
from bb_paxdata.interfaces.api.schemas import ReviewerResponse, SystemSettingsSchema

router = APIRouter(prefix="/settings", tags=["Settings"])

_SYSTEM_SETTINGS_FILE = Path("data/system_settings.json")

_DEFAULT_SYSTEM_SETTINGS = {
    "anomaly_soft_log_only": False,
    "anomaly_controller_enabled": True,
    "anomaly_context_window": 5,
    "risk_ai_weight": 0.6,
    "risk_anomaly_weight": 0.4,
    "formula_tolerance": 0.01,
    "risk_threshold": 70.0,
}


def _load_system_settings() -> dict:
    """Load system settings from JSON file, falling back to defaults from config."""
    if _SYSTEM_SETTINGS_FILE.exists():
        try:
            with open(_SYSTEM_SETTINGS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    cfg = get_settings()
    return {
        "anomaly_soft_log_only": cfg.anomaly_soft_log_only,
        "anomaly_controller_enabled": cfg.anomaly_controller_enabled,
        "anomaly_context_window": cfg.anomaly_context_window,
        "risk_ai_weight": cfg.risk_ai_weight,
        "risk_anomaly_weight": cfg.risk_anomaly_weight,
        "formula_tolerance": cfg.formula_tolerance,
        "risk_threshold": cfg.risk_threshold,
    }


def _save_system_settings(data: dict) -> None:
    """Persist system settings to JSON file."""
    _SYSTEM_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SYSTEM_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@router.get("/reviewers", response_model=list[ReviewerResponse])
async def get_reviewers(
    db: AsyncSession = Depends(get_db),
    _has_permission: bool = Depends(PermissionChecker("admin")),
) -> list[ReviewerResponse]:
    """Retrieve all reviewer configurations, seeding default assignments if empty."""
    from sqlalchemy import select

    from bb_paxdata.infrastructure.db.models import ReviewerAssignment
    from bb_paxdata.infrastructure.db.repositories.reviewer_assignment import (
        ReviewerAssignmentRepository,
    )

    repo = ReviewerAssignmentRepository(db)
    stmt = select(ReviewerAssignment)
    res = await db.execute(stmt)
    rows = list(res.scalars().all())

    if not rows:
        await repo.seed_default_assignments()
        await db.commit()
        res = await db.execute(stmt)
        rows = list(res.scalars().all())

    return [
        ReviewerResponse(
            reviewer_id=r.reviewer_id,
            scope_type=r.scope_type,
            scope_value=r.scope_value,
            permission_level=r.permission_level,
            max_daily_reviews=r.max_daily_reviews,
            current_daily_count=r.current_daily_count,
            is_active=r.is_active,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.get("/system", response_model=SystemSettingsSchema)
async def get_system_settings(
    _has_permission: bool = Depends(PermissionChecker("admin")),
) -> SystemSettingsSchema:
    """Retrieve current system settings (from persisted JSON or runtime defaults)."""
    data = _load_system_settings()
    # Fill any missing keys with defaults to be forward-compatible
    merged = {**_DEFAULT_SYSTEM_SETTINGS, **data}
    return SystemSettingsSchema(**merged)


@router.put("/system", response_model=SystemSettingsSchema)
async def update_system_settings(
    payload: SystemSettingsSchema,
    _has_permission: bool = Depends(PermissionChecker("admin")),
) -> SystemSettingsSchema:
    """Persist updated system settings to JSON file."""
    try:
        _save_system_settings(payload.model_dump())
        # Dynamically update the active Settings singleton at runtime
        cfg = get_settings()
        for field, value in payload.model_dump().items():
            if hasattr(cfg, field):
                setattr(cfg, field, value)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Settings could not be saved: {exc}",
        )
    return payload
