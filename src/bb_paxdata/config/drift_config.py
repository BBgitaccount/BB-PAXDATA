"""Drift detection configuration."""

from pydantic import BaseModel, Field


class DriftConfig(BaseModel):
    """Configuration for drift detection thresholds and windows."""

    psi_warning_threshold: float = Field(
        default=0.1, ge=0.0, le=1.0, description="PSI warning threshold"
    )
    psi_critical_threshold: float = Field(
        default=0.2, ge=0.0, le=1.0, description="PSI critical threshold"
    )
    ks_warning_pvalue: float = Field(
        default=0.05, ge=0.0, le=1.0, description="KS test p-value warning threshold"
    )
    wasserstein_warning: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Wasserstein warning threshold"
    )
    wasserstein_critical: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Wasserstein critical threshold"
    )
    concept_drift_window_days: int = Field(
        default=7, ge=1, le=90, description="Concept drift window in days"
    )
    baseline_window_days: int = Field(
        default=30, ge=7, le=365, description="Baseline window in days"
    )
    alert_cooldown_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Suppress duplicate alerts per field within this window (hours)",
    )
