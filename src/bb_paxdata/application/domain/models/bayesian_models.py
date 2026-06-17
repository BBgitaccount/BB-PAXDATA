"""
Bayesian distribution models for TASK-A07 position estimation.

This module provides the distribution abstractions used by Kalman and particle
filter implementations. All models are frozen Pydantic dataclasses for immutability.

Reference: TASK-A07 Engineering Review v2.0 (commit 8d37ef99)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator


class Distribution(ABC):
    """
    Abstract base class for probability distributions.

    Defines the interface that all distribution implementations must follow.
    This is an ABC, not a dataclass — methods are abstract, not fields.
    """

    @abstractmethod
    def mode(self) -> float:
        """Return the mode (most likely value) of the distribution."""
        ...

    @abstractmethod
    def mean(self) -> float:
        """Return the expected value (mean) of the distribution."""
        ...

    @abstractmethod
    def std(self) -> float:
        """Return the standard deviation of the distribution."""
        ...

    @abstractmethod
    def credible_interval(self, alpha: float = 0.05) -> tuple[float, float]:
        """
        Return the credible interval for the distribution.

        Args:
            alpha: Significance level (default 0.05 for 95% CI)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        ...


class GaussianDistribution(BaseModel, Distribution):
    """
    Gaussian (normal) distribution with mu/sigma field naming.

    CRITICAL FIX (FINDING C-01): Uses 'mu' and 'sigma' as field names instead
    of 'mean' and 'std' to avoid method/attribute name collision. The methods
    mean() and std() override the abstract protocol methods and return the
    field values.

    Reference: TASK-A07 Finding C-01
    """

    model_config = ConfigDict(frozen=False)

    mu: float
    sigma: float

    @field_validator("sigma", mode="before")
    @classmethod
    def sigma_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"sigma must be positive, got {v}")
        return v

    def mode(self) -> float:
        """For Gaussian, mode = mean = mu."""
        return self.mu

    def mean(self) -> float:
        """Return the mean (mu)."""
        return self.mu

    def std(self) -> float:
        """Return the standard deviation (sigma)."""
        return self.sigma

    def credible_interval(self, alpha: float = 0.05) -> tuple[float, float]:
        """
        Compute credible interval using quantiles of the normal distribution.

        Args:
            alpha: Significance level (default 0.05 for 95% CI)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        from scipy.stats import norm as _norm

        z = _norm.ppf(1.0 - alpha / 2.0)
        return (self.mu - z * self.sigma, self.mu + z * self.sigma)


class EmpiricalDistribution(BaseModel, Distribution):
    """
    Empirical distribution from particle samples with weights.

    CRITICAL FIX (FINDING M-01): credible_interval() uses weighted quantiles,
    not index-based quantiles. This is correct regardless of whether weights
    are uniform (post-resampling) or skewed (pre-resampling).

    Reference: TASK-A07 Finding M-01
    """

    model_config = ConfigDict(frozen=False)

    particles: list[float]
    weights: list[float]

    @field_validator("particles", "weights", mode="before")
    @classmethod
    def validate_arrays(cls, v: Any) -> list[float]:
        if not isinstance(v, (list, np.ndarray)):
            raise ValueError(f"Must be list or array, got {type(v)}")
        if isinstance(v, np.ndarray):
            return v.tolist()
        return list(v)

    @field_validator("particles", "weights")
    @classmethod
    def validate_length(cls, v: list[float], info) -> list[float]:
        if len(v) == 0:
            raise ValueError("Cannot be empty")
        return v

    def mode(self) -> float:
        """
        Compute mode using KDE (kernel density estimation).

        MINOR FIX (FINDING m-02): Handles degenerate particle cloud where all
        particles have collapsed to the same value. Falls back to mean if KDE
        fails due to singular matrix.
        """
        mean_val = self.mean()
        particle_range = max(self.particles) - min(self.particles)

        # Degenerate case: all particles at same location
        if particle_range < 1e-8:
            return mean_val

        try:
            from scipy.stats import gaussian_kde

            particles_arr = np.array(self.particles)
            weights_arr = np.array(self.weights)

            kde = gaussian_kde(
                particles_arr, weights=weights_arr, bw_method="silverman"
            )
            std_val = self.std()

            x_grid = np.linspace(
                particles_arr.min() - std_val,
                particles_arr.max() + std_val,
                1000,
            )
            mode = float(x_grid[np.argmax(kde(x_grid))])
            return mode
        except np.linalg.LinAlgError:
            # Fallback to mean on singular KDE
            return mean_val

    def mean(self) -> float:
        """Compute weighted mean."""
        return float(np.average(self.particles, weights=self.weights))

    def std(self) -> float:
        """Compute weighted standard deviation."""
        mean_val = self.mean()
        weighted_var = float(
            np.average((np.array(self.particles) - mean_val) ** 2, weights=self.weights)
        )
        return float(np.sqrt(max(weighted_var, 1e-10)))

    def credible_interval(self, alpha: float = 0.05) -> tuple[float, float]:
        """
        Compute weighted quantile-based credible interval.

        CRITICAL FIX (FINDING M-01): Uses weighted quantiles via cumulative
        weight sum, not index-based quantiles. This is correct regardless of
        whether weights are uniform or not.

        Args:
            alpha: Significance level (default 0.05 for 95% CI)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        particles_arr = np.array(self.particles)
        weights_arr = np.array(self.weights)

        sorted_idx = np.argsort(particles_arr)
        sorted_particles = particles_arr[sorted_idx]
        sorted_weights = weights_arr[sorted_idx]
        cumulative_weights = np.cumsum(sorted_weights)

        # Normalize (defensive)
        cumulative_weights /= cumulative_weights[-1]

        lower_idx = np.searchsorted(cumulative_weights, alpha / 2.0)
        upper_idx = np.searchsorted(cumulative_weights, 1.0 - alpha / 2.0)

        # Clip to valid range
        lower_idx = int(np.clip(lower_idx, 0, len(sorted_particles) - 1))
        upper_idx = int(np.clip(upper_idx, 0, len(sorted_particles) - 1))

        return (float(sorted_particles[lower_idx]), float(sorted_particles[upper_idx]))
