"""Drift Metrics Service - Statistical drift detection algorithms.

Pure functions for computing drift metrics between baseline and current distributions.
No side effects, no DB calls.
"""

from datetime import datetime
from typing import Literal

import numpy as np
import scipy.stats
from pydantic import BaseModel

from bb_paxdata.config.settings import get_settings


class DriftScore(BaseModel):
    """Output model for drift metric computation."""

    metric: str  # "PSI" | "KL" | "KS" | "Wasserstein"
    field: str  # "sentiment_score" | "risk_score" | "ai_confidence"
    value: float
    severity: Literal["stable", "warning", "critical"]
    metadata: dict = {}
    measured_at: datetime
    baseline_window_start: datetime
    baseline_window_end: datetime
    current_window_start: datetime
    current_window_end: datetime


def compute_psi(
    baseline: np.ndarray,
    current: np.ndarray,
    field: str,
    baseline_window_start: datetime,
    baseline_window_end: datetime,
    current_window_start: datetime,
    current_window_end: datetime,
) -> DriftScore:
    """Compute Population Stability Index (PSI).

    Bins both arrays into 10 equal-width buckets spanning [0.0, 1.0].
    Computes expected % (baseline) and observed % (current) per bucket.
    Replaces any zero bucket with 0.0001 before division.

    Thresholds:
        < 0.1: stable
        0.1 - 0.2: warning
        > 0.2: critical

    Args:
        baseline: Baseline distribution array
        current: Current distribution array
        field: Field name being measured
        baseline_window_start: Start of baseline window
        baseline_window_end: End of baseline window
        current_window_start: Start of current window
        current_window_end: End of current window

    Returns:
        DriftScore with PSI value and severity
    """
    settings = get_settings()
    psi_warning_threshold = getattr(settings, "psi_warning_threshold", 0.1)
    psi_critical_threshold = getattr(settings, "psi_critical_threshold", 0.2)

    # Bin into 10 equal-width buckets spanning [0.0, 1.0]
    bins = np.linspace(0.0, 1.0, 11)  # 10 bins = 11 edges
    baseline_hist, _ = np.histogram(baseline, bins=bins)
    current_hist, _ = np.histogram(current, bins=bins)

    # Convert to percentages
    baseline_pct = baseline_hist / len(baseline)
    current_pct = current_hist / len(current)

    # Replace zeros with 0.0001 to avoid division by zero
    baseline_pct = np.where(baseline_pct == 0, 0.0001, baseline_pct)
    current_pct = np.where(current_pct == 0, 0.0001, current_pct)

    # Compute PSI: Σ (observed% - expected%) × ln(observed% / expected%)
    psi = np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct))

    # Determine severity
    if psi < psi_warning_threshold:
        severity = "stable"
    elif psi < psi_critical_threshold:
        severity = "warning"
    else:
        severity = "critical"

    return DriftScore(
        metric="PSI",
        field=field,
        value=float(psi),
        severity=severity,
        metadata={
            "baseline_count": len(baseline),
            "current_count": len(current),
            "bins": bins.tolist(),
        },
        measured_at=datetime.utcnow(),
        baseline_window_start=baseline_window_start,
        baseline_window_end=baseline_window_end,
        current_window_start=current_window_start,
        current_window_end=current_window_end,
    )


def compute_kl(
    baseline: np.ndarray,
    current: np.ndarray,
    field: str,
    baseline_window_start: datetime,
    baseline_window_end: datetime,
    current_window_start: datetime,
    current_window_end: datetime,
) -> DriftScore:
    """Compute KL Divergence (Jeffrey Divergence).

    Builds histograms with 10 bins and normalizes to probability distributions.
    Applies Laplace smoothing with epsilon = 1e-10.
    Computes both KL(current || baseline) and KL(baseline || current) via scipy.stats.entropy.
    Returns their average (Jeffrey divergence).

    Thresholds:
        ≤ 0.5: stable
        0.5 - 1.0: warning
        > 1.0: critical

    Args:
        baseline: Baseline distribution array
        current: Current distribution array
        field: Field name being measured
        baseline_window_start: Start of baseline window
        baseline_window_end: End of baseline window
        current_window_start: Start of current window
        current_window_end: End of current window

    Returns:
        DriftScore with KL divergence value and severity
    """
    # Build histograms with 10 bins
    bins = 10
    baseline_hist, _ = np.histogram(baseline, bins=bins, range=(0.0, 1.0))
    current_hist, _ = np.histogram(current, bins=bins, range=(0.0, 1.0))

    # Normalize to probability distributions with Laplace smoothing
    epsilon = 1e-10
    baseline_dist = (baseline_hist + epsilon) / (np.sum(baseline_hist) + epsilon * bins)
    current_dist = (current_hist + epsilon) / (np.sum(current_hist) + epsilon * bins)

    # Compute KL divergences
    kl_current_baseline = scipy.stats.entropy(current_dist, baseline_dist)
    kl_baseline_current = scipy.stats.entropy(baseline_dist, current_dist)

    # Jeffrey divergence (average)
    jeffrey_divergence = (kl_current_baseline + kl_baseline_current) / 2.0

    # Determine severity
    if jeffrey_divergence <= 0.5:
        severity = "stable"
    elif jeffrey_divergence <= 1.0:
        severity = "warning"
    else:
        severity = "critical"

    return DriftScore(
        metric="KL",
        field=field,
        value=float(jeffrey_divergence),
        severity=severity,
        metadata={
            "kl_current_baseline": float(kl_current_baseline),
            "kl_baseline_current": float(kl_baseline_current),
            "baseline_count": len(baseline),
            "current_count": len(current),
        },
        measured_at=datetime.utcnow(),
        baseline_window_start=baseline_window_start,
        baseline_window_end=baseline_window_end,
        current_window_start=current_window_start,
        current_window_end=current_window_end,
    )


def compute_ks(
    baseline: np.ndarray,
    current: np.ndarray,
    field: str,
    baseline_window_start: datetime,
    baseline_window_end: datetime,
    current_window_start: datetime,
    current_window_end: datetime,
) -> DriftScore:
    """Compute Kolmogorov-Smirnov test statistic.

    Calls scipy.stats.ks_2samp directly on raw arrays (no histogram).
    Stores statistic as DriftScore.value and p_value in metadata.

    Thresholds:
        statistic ≤ 0.1 OR p_value ≥ 0.05: stable
        statistic > 0.1 AND p_value < 0.05: warning

    Args:
        baseline: Baseline distribution array
        current: Current distribution array
        field: Field name being measured
        baseline_window_start: Start of baseline window
        baseline_window_end: End of baseline window
        current_window_start: Start of current window
        current_window_end: End of current window

    Returns:
        DriftScore with KS statistic and severity
    """
    settings = get_settings()
    ks_warning_pvalue = getattr(settings, "ks_warning_pvalue", 0.05)

    # Compute KS test
    statistic, p_value = scipy.stats.ks_2samp(baseline, current)

    # Determine severity
    if statistic <= 0.1 or p_value >= ks_warning_pvalue:
        severity = "stable"
    else:
        severity = "warning"

    return DriftScore(
        metric="KS",
        field=field,
        value=float(statistic),
        severity=severity,
        metadata={
            "p_value": float(p_value),
            "baseline_count": len(baseline),
            "current_count": len(current),
        },
        measured_at=datetime.utcnow(),
        baseline_window_start=baseline_window_start,
        baseline_window_end=baseline_window_end,
        current_window_start=current_window_start,
        current_window_end=current_window_end,
    )


def compute_wasserstein(
    baseline: np.ndarray,
    current: np.ndarray,
    field: str,
    baseline_window_start: datetime,
    baseline_window_end: datetime,
    current_window_start: datetime,
    current_window_end: datetime,
) -> DriftScore:
    """Compute Wasserstein Distance (Earth Mover's Distance).

    Calls scipy.stats.wasserstein_distance on raw arrays.
    Normalizes: value = raw_distance / (max_val - min_val)
    where max_val/min_val are global domain bounds (typically 1.0 and 0.0).

    Thresholds:
        ≤ 0.05: stable
        0.05 - 0.15: warning
        > 0.15: critical

    Args:
        baseline: Baseline distribution array
        current: Current distribution array
        field: Field name being measured
        baseline_window_start: Start of baseline window
        baseline_window_end: End of baseline window
        current_window_start: Start of current window
        current_window_end: End of current window

    Returns:
        DriftScore with normalized Wasserstein distance and severity
    """
    settings = get_settings()
    wasserstein_warning = getattr(settings, "wasserstein_warning", 0.05)
    wasserstein_critical = getattr(settings, "wasserstein_critical", 0.15)

    # Compute raw Wasserstein distance
    raw_distance = scipy.stats.wasserstein_distance(baseline, current)

    # Normalize by domain bounds (typically [0.0, 1.0])
    max_val = 1.0
    min_val = 0.0
    domain_range = max_val - min_val
    normalized_value = raw_distance / domain_range if domain_range > 0 else 0.0

    # Determine severity
    if normalized_value <= wasserstein_warning:
        severity = "stable"
    elif normalized_value <= wasserstein_critical:
        severity = "warning"
    else:
        severity = "critical"

    return DriftScore(
        metric="Wasserstein",
        field=field,
        value=float(normalized_value),
        severity=severity,
        metadata={
            "raw_distance": float(raw_distance),
            "domain_range": domain_range,
            "baseline_count": len(baseline),
            "current_count": len(current),
        },
        measured_at=datetime.utcnow(),
        baseline_window_start=baseline_window_start,
        baseline_window_end=baseline_window_end,
        current_window_start=current_window_start,
        current_window_end=current_window_end,
    )
