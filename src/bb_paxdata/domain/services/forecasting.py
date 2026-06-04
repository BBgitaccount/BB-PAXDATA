# src/bb_paxdata/domain/services/forecasting.py
from __future__ import annotations

from typing import Sequence

import numpy as np

from bb_paxdata.domain.models.forecast import ForecastResult, TimeSlice


class EWMA:
    """Vectorized EWMA with optional bias correction."""

    def __init__(self, alpha: float = 0.3) -> None:
        self.alpha = alpha

    def fit(self, series: np.ndarray) -> np.ndarray:
        """Return EWMA smoothed series."""
        if len(series) == 0:
            return series
        smoothed = np.zeros_like(series)
        smoothed[0] = series[0]
        for t in range(1, len(series)):
            smoothed[t] = self.alpha * series[t] + (1 - self.alpha) * smoothed[t - 1]
        return smoothed

    def forecast_next(self, series: np.ndarray) -> float:
        smoothed = self.fit(series)
        return float(smoothed[-1])


class ChangepointDetector:
    """Simple CUSUM-based changepoint flag."""

    def __init__(self, threshold: float = 2.0) -> None:
        self.threshold = threshold

    def is_stable(self, series: np.ndarray) -> bool:
        if len(series) < 4:
            return True
        mean = np.mean(series)
        std = np.std(series, ddof=1)
        if std == 0:
            return True
        cusum_pos = 0.0
        cusum_neg = 0.0
        for val in series:
            cusum_pos = max(0, cusum_pos + (val - mean) / std - 0.5)
            cusum_neg = min(0, cusum_neg + (val - mean) / std + 0.5)
            if cusum_pos > self.threshold or abs(cusum_neg) > self.threshold:
                return False
        return True


class RiskForecaster:
    def __init__(
        self,
        alpha_mean: float = 0.3,
        alpha_vol: float = 0.25,
        changepoint_threshold: float = 2.5,
        monte_carlo_sims: int = 5000,
    ) -> None:
        self._ewma_mean = EWMA(alpha_mean)
        self._ewma_vol = EWMA(alpha_vol)
        self._cpd = ChangepointDetector(changepoint_threshold)
        self._mc_sims = monte_carlo_sims

    def forecast_next_panel_risk(
        self, historical: Sequence[TimeSlice], min_history: int = 5
    ) -> ForecastResult:
        if len(historical) < min_history:
            last_risk = historical[-1].computed_risk if historical else 0.0
            return ForecastResult(
                predicted_risk=last_risk,
                trend=0.0,
                volatility_forecast=0.0,
                confidence_lower=max(0.0, last_risk - 1.0),
                confidence_upper=min(10.0, last_risk + 1.0),
                regime_stable=True,
            )

        risks = np.array([h.computed_risk for h in historical], dtype=np.float32)
        vols = np.array([h.sentiment_volatility for h in historical], dtype=np.float32)
        dkis = np.array(
            [h.keyness_index_deviation for h in historical], dtype=np.float32
        )
        escalations = np.array(
            [h.escalation_multiplier for h in historical], dtype=np.float32
        )

        # 1. Regime check
        stable = self._cpd.is_stable(risks)

        # 2. EWMA mean & vol
        ewma_risk = self._ewma_mean.fit(risks)
        ewma_vol = self._ewma_vol.fit(vols)
        current_risk = ewma_risk[-1]
        current_vol = ewma_vol[-1]
        trend = float(current_risk - ewma_risk[-2]) if len(ewma_risk) > 1 else 0.0

        # 3. Composite feature projection
        next_dki = self._ewma_mean.forecast_next(dkis)
        next_esc = escalations[-1]  # hold-last-value for escalation

        # 4. Risk projection formula (domain-specific composite)
        projected_score = (
            current_risk
            + 0.4 * trend
            + 0.3 * current_vol * next_esc
            + 0.2 * abs(next_dki)
        )
        projected_score = float(np.clip(projected_score, 0.0, 10.0))

        # 5. Monte Carlo confidence interval
        # Parametric bootstrap: assume normal with EWMA vol
        rng = np.random.default_rng(42)
        simulations = rng.normal(
            loc=projected_score, scale=current_vol + 1e-6, size=self._mc_sims
        )
        simulations = np.clip(simulations, 0.0, 10.0)
        ci_lower = float(np.percentile(simulations, 2.5))
        ci_upper = float(np.percentile(simulations, 97.5))

        return ForecastResult(
            predicted_risk=projected_score,
            trend=trend,
            volatility_forecast=float(current_vol),
            confidence_lower=ci_lower,
            confidence_upper=ci_upper,
            regime_stable=stable,
        )
