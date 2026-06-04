# src/bb_paxdata/domain/models/forecast.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TimeSlice(BaseModel):
    model_config = ConfigDict(frozen=True)

    panel_id: str
    timestamp: datetime
    sentiment_delta: float  # S_t
    sentiment_volatility: float  # σ_t (realized or EWMA)
    keyness_index_deviation: float  # DKI_t
    escalation_multiplier: float = Field(default=1.0, ge=0.0)
    computed_risk: float = Field(..., ge=0.0, le=10.0)


class ForecastResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    predicted_risk: float = Field(..., ge=0.0, le=10.0)
    trend: float  # slope of EWMA mean
    volatility_forecast: float
    confidence_lower: float
    confidence_upper: float
    regime_stable: bool  # False if changepoint detected in last W panels
    forecast_horizon_panels: int = 1
