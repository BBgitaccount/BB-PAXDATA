# src/bb_paxdata/domain/models/forecast.py
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimeSlice(BaseModel):
    model_config = ConfigDict(frozen=False)

    panel_id: str
    timestamp: datetime
    sentiment_delta: float  # S_t
    sentiment_volatility: float  # σ_t (realized or EWMA)
    keyness_index_deviation: float  # DKI_t
    escalation_multiplier: float = Field(default=1.0, ge=0.0)
    computed_risk: float = Field(..., ge=0.0, le=10.0)


class ForecastResult(BaseModel):
    model_config = ConfigDict(frozen=False)

    predicted_risk: float = Field(..., ge=0.0, le=10.0)
    trend: float  # slope of EWMA mean
    volatility_forecast: float
    confidence_lower: float
    confidence_upper: float
    regime_stable: bool  # False if changepoint detected in last W panels
    forecast_horizon_panels: int = 1
    # Bayesian extension fields — populated only when Bayesian path active
    credible_interval_95: tuple[float, float] = Field(
        default=(float("nan"), float("nan"))
    )
    posterior_mode: float = Field(default=float("nan"))
    posterior_mean: float = Field(default=float("nan"))
    posterior_std: float = Field(default=float("nan"))
    filter_type: Literal["ewma", "kalman", "particle"] = "ewma"
    # signal_strength: NOT populated by RiskForecaster — belongs to DKIAssembler context
    # Consumers must check filter_type != "ewma" before using Bayesian fields.

    @field_validator("credible_interval_95", mode="before")
    @classmethod
    def parse_ci_from_json(
        cls, v: tuple[float, float] | list[float] | str
    ) -> tuple[float, float]:
        """Parse credible interval from JSON or tuple format."""
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return (v[0], v[1])
        if isinstance(v, str):
            import json as _json

            parsed = _json.loads(v)
            return (float(parsed[0]), float(parsed[1]))
        return (float("nan"), float("nan"))
