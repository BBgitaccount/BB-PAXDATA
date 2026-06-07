"""
Unit tests for Bayesian position tracking components (TASK-A07).

Tests cover critical regression cases from the engineering review:
- C-01: GaussianDistribution method/attribute collision
- C-02: filterpy dependency removal
- C-03: update() returns None (stub) vs BayesianUpdateResult
- M-01: EmpiricalDistribution weight-aware credible interval
- M-03: engagement_boost weight contribution
- m-01: ESS-gated resampling
- m-02: degeneracy-safe KDE

Reference: TASK-A07 Engineering Review v2.0 (commit 8d37ef99)
"""

import numpy as np
import pytest
from bb_paxdata.application.domain.models.bayesian_models import (
    EmpiricalDistribution,
    GaussianDistribution,
)
from bb_paxdata.application.domain.services.bayesian_position_tracker import (
    BayesianPositionTracker,
    BayesianUpdateResult,
    KalmanPositionTracker,
    ParticleFilterPositionTracker,
    calculate_signal_strength,
    classify_signal_type,
)


class TestGaussianDistribution:
    """Tests for GaussianDistribution model."""

    def test_kalman_no_recursion_error(self):
        """Regression test for FINDING C-01: GaussianDistribution method collision."""
        dist = GaussianDistribution(mu=0.0, sigma=1.0)
        assert dist.mean() == 0.0  # Must not recurse
        assert dist.std() == 1.0  # Must not recurse
        ci = dist.credible_interval()
        assert ci[0] < 0.0 < ci[1]
        assert isinstance(ci, tuple)
        assert len(ci) == 2

    def test_sigma_validation(self):
        """Test that sigma must be positive."""
        with pytest.raises(ValueError, match="sigma must be positive"):
            GaussianDistribution(mu=0.0, sigma=0.0)
        with pytest.raises(ValueError, match="sigma must be positive"):
            GaussianDistribution(mu=0.0, sigma=-1.0)

    def test_mode_equals_mean_for_gaussian(self):
        """For Gaussian, mode = mean = mu."""
        dist = GaussianDistribution(mu=1.5, sigma=0.5)
        assert dist.mode() == 1.5
        assert dist.mean() == 1.5

    def test_credible_interval_width(self):
        """Test credible interval width scales with sigma."""
        dist_narrow = GaussianDistribution(mu=0.0, sigma=0.1)
        dist_wide = GaussianDistribution(mu=0.0, sigma=1.0)
        ci_narrow = dist_narrow.credible_interval()
        ci_wide = dist_wide.credible_interval()
        assert (ci_wide[1] - ci_wide[0]) > (ci_narrow[1] - ci_narrow[0])


class TestEmpiricalDistribution:
    """Tests for EmpiricalDistribution model."""

    def test_empirical_distribution_weighted_ci(self):
        """Regression test for FINDING M-01: weight-aware credible interval."""
        particles = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        # Heavily weight the high-value particles
        weights = np.array([0.01, 0.01, 0.01, 0.01, 0.96])
        weights /= weights.sum()
        dist = EmpiricalDistribution(
            particles=particles.tolist(), weights=weights.tolist()
        )
        ci = dist.credible_interval(alpha=0.05)
        # CI should be near 4.0, not straddling 0-4 uniformly
        assert ci[0] > 2.0, "Weighted CI lower bound must reflect weight concentration"
        assert ci[1] <= 4.0

    def test_weighted_mean(self):
        """Test that mean uses weights."""
        particles = [0.0, 1.0, 2.0]
        weights = [0.1, 0.1, 0.8]
        dist = EmpiricalDistribution(particles=particles, weights=weights)
        # Weighted mean should be close to 2.0 (highest weight)
        assert dist.mean() == pytest.approx(1.7, abs=0.1)

    def test_weighted_std(self):
        """Test that std uses weights."""
        particles = [0.0, 1.0, 2.0]
        weights = [0.1, 0.1, 0.8]
        dist = EmpiricalDistribution(particles=particles, weights=weights)
        std = dist.std()
        assert std > 0.0
        assert std < 2.0  # Should be lower than unweighted std

    def test_mode_with_uniform_weights(self):
        """Test mode computation with uniform weights."""
        particles = [0.0, 1.0, 2.0, 3.0, 4.0]
        weights = [0.2, 0.2, 0.2, 0.2, 0.2]
        dist = EmpiricalDistribution(particles=particles, weights=weights)
        mode = dist.mode()
        assert 0.0 <= mode <= 4.0

    def test_mode_with_degenerate_particles(self):
        """Regression test for FINDING m-02: degeneracy-safe KDE."""
        # Force all particles to single point
        particles = [1.5, 1.5, 1.5, 1.5, 1.5]
        weights = [0.2, 0.2, 0.2, 0.2, 0.2]
        dist = EmpiricalDistribution(particles=particles, weights=weights)
        # Must not raise LinAlgError
        mode = dist.mode()
        assert mode == pytest.approx(1.5, abs=1e-6)

    def test_validation_empty_arrays(self):
        """Test that empty arrays are rejected."""
        with pytest.raises(ValueError, match="Cannot be empty"):
            EmpiricalDistribution(particles=[], weights=[0.5])
        with pytest.raises(ValueError, match="Cannot be empty"):
            EmpiricalDistribution(particles=[1.0], weights=[])


class TestKalmanPositionTracker:
    """Tests for KalmanPositionTracker."""

    def test_kalman_tracker_no_filterpy(self):
        """Regression test for FINDING C-02: filterpy removal."""
        import sys

        assert "filterpy" not in sys.modules, "filterpy must not be imported"
        tracker = KalmanPositionTracker()
        tracker.predict()
        mean, std = tracker.update(0.5, measurement_noise=0.3)
        assert isinstance(mean, float)
        assert isinstance(std, float)
        assert std < 3.0  # Should reduce from initial covariance

    def test_predict_update_cycle(self):
        """Test standard predict-update cycle."""
        tracker = KalmanPositionTracker(
            initial_position=0.0, initial_covariance=1.0, process_noise=0.1
        )
        tracker.predict()
        mean, std = tracker.update(1.0)
        assert mean > 0.0  # Should move toward observation
        assert std < 1.0  # Uncertainty should decrease

    def test_time_gap_adjusted_process_noise(self):
        """Test that time gap increases process noise."""
        tracker = KalmanPositionTracker(process_noise=0.1)
        # Small gap
        tracker.predict(delta_t_days=0.1, base_process_noise=0.1)
        # Large gap
        tracker.predict(delta_t_days=10.0, base_process_noise=0.1)
        # Posterior variance should be larger after large gap
        assert tracker.posterior_variance > 0.1

    def test_measurement_noise_override(self):
        """Test measurement noise override in update."""
        tracker = KalmanPositionTracker(measurement_noise=0.5)
        tracker.predict()
        # Override with lower noise
        mean, std = tracker.update(1.0, measurement_noise=0.1)
        # Lower noise should result in lower posterior std
        assert std < 0.5

    def test_posterior_properties(self):
        """Test posterior mean and variance properties."""
        tracker = KalmanPositionTracker(initial_position=1.5, initial_covariance=2.0)
        assert tracker.posterior_mean == 1.5
        assert tracker.posterior_variance == 2.0


class TestParticleFilterPositionTracker:
    """Tests for ParticleFilterPositionTracker."""

    def test_particle_filter_ess_gated_resampling(self):
        """Regression test for FINDING m-01: ESS-gated resampling."""
        tracker = ParticleFilterPositionTracker(particle_count=1000)
        initial_particle_variance = float(np.var(tracker.particles))
        tracker.update(observation=0.5, signal_strength=0.05)  # Very weak signal
        post_particle_variance = float(np.var(tracker.particles))
        # Weak signal: ESS should be high → no resampling → diversity preserved
        assert (
            post_particle_variance > initial_particle_variance * 0.8
        ), "Weak signal update must preserve particle diversity via ESS gate"

    def test_particle_filter_strong_signal(self):
        """Test that strong signal triggers resampling."""
        tracker = ParticleFilterPositionTracker(particle_count=1000)
        tracker.update(observation=2.0, signal_strength=0.9)  # Strong signal
        # Strong signal should trigger resampling
        ess = tracker.effective_sample_size()
        assert (
            ess < tracker.N * 0.5
        ), "Strong signal should reduce ESS and trigger resampling"

    def test_effective_sample_size(self):
        """Test ESS calculation."""
        tracker = ParticleFilterPositionTracker(particle_count=1000)
        # Uniform weights → maximum ESS
        ess_uniform = tracker.effective_sample_size()
        assert ess_uniform == pytest.approx(1000, abs=10)

        # Skewed weights → lower ESS
        tracker.weights = np.array([0.99] + [0.01 / 999] * 999)
        ess_skewed = tracker.effective_sample_size()
        assert ess_skewed < ess_uniform

    def test_particle_filter_degenerate_recovery(self):
        """Regression test for FINDING m-02: KDE degeneracy handling."""
        tracker = ParticleFilterPositionTracker(particle_count=100)
        # Force all particles to single point
        tracker.particles = np.full(100, 1.5)
        tracker.weights = np.ones(100) / 100
        # Must not raise LinAlgError
        mode, mean, ci = tracker.get_posterior()
        assert mode == pytest.approx(1.5, abs=1e-6)
        assert mean == pytest.approx(1.5, abs=1e-6)

    def test_get_posterior_std(self):
        """Test posterior std calculation."""
        tracker = ParticleFilterPositionTracker(particle_count=100)
        std = tracker.get_posterior_std()
        assert std > 0.0
        assert std < 10.0  # Reasonable bound

    def test_predict_step(self):
        """Test predict step adds process noise."""
        tracker = ParticleFilterPositionTracker(particle_count=100, process_noise=0.5)
        initial_particles = tracker.particles.copy()
        tracker.predict()
        # Particles should have changed due to process noise
        assert not np.allclose(tracker.particles, initial_particles)


class TestBayesianPositionTracker:
    """Tests for BayesianPositionTracker wrapper."""

    def test_update_returns_bayesian_update_result(self):
        """Regression test for FINDING C-03: update() must not return None."""
        tracker = BayesianPositionTracker(speaker_id="test", filter_type="particle")
        result = tracker.update(observation=0.5, signal_strength=0.7)
        assert result is not None, "update() returned None (stub not implemented)"
        assert isinstance(result, BayesianUpdateResult)
        assert isinstance(result.posterior_mean, float)
        assert result.credible_interval_95[0] is not None

    def test_kalman_filter_type(self):
        """Test Kalman filter mode."""
        tracker = BayesianPositionTracker(speaker_id="test", filter_type="kalman")
        result = tracker.update(observation=1.0, signal_strength=0.8)
        assert result.filter_type == "kalman"
        assert np.isnan(result.ess)  # ESS is NaN for Kalman

    def test_particle_filter_type(self):
        """Test particle filter mode."""
        tracker = BayesianPositionTracker(speaker_id="test", filter_type="particle")
        result = tracker.update(observation=1.0, signal_strength=0.8)
        assert result.filter_type == "particle"
        assert not np.isnan(result.ess)  # ESS is valid for particle filter

    def test_speaker_id_propagation(self):
        """Test speaker_id is propagated to result."""
        tracker = BayesianPositionTracker(
            speaker_id="speaker_123", filter_type="kalman"
        )
        result = tracker.update(observation=0.0, signal_strength=0.5)
        assert result.speaker_id == "speaker_123"

    def test_delta_t_days_parameter(self):
        """Test delta_t_days parameter is passed through."""
        tracker = BayesianPositionTracker(speaker_id="test", filter_type="kalman")
        result = tracker.update(observation=0.0, signal_strength=0.5, delta_t_days=5.0)
        assert result.posterior_mean is not None


class TestSignalStrengthCalculation:
    """Tests for signal strength calculation."""

    def test_signal_strength_engagement_contribution(self):
        """Regression test for FINDING M-03: engagement_boost weight."""
        # Identical setup except engagement type
        speech_act_score = 0.8
        graduation_score = 0.5
        hedging_penalty = 0.3

        strength_mono = calculate_signal_strength(
            speech_act_score,
            graduation_score,
            is_monogloss=True,
            hedging_penalty=hedging_penalty,
        )
        strength_hetero = calculate_signal_strength(
            speech_act_score,
            graduation_score,
            is_monogloss=False,
            hedging_penalty=hedging_penalty,
        )

        diff = strength_mono - strength_hetero
        assert diff >= 0.05, (
            f"MONOGLOSS must score >= 0.05 higher than HETEROGLOSS; got {diff:.4f}. "
            "Check engagement_boost weight (must not be 0.1 * ±0.1)."
        )

    def test_signal_strength_clamping(self):
        """Test signal strength is clamped to [0, 1]."""
        # Very high values should clamp to 1.0
        strength = calculate_signal_strength(
            speech_act_score=1.0,
            graduation_score=1.0,
            is_monogloss=True,
            hedging_penalty=0.0,
        )
        assert strength == 1.0

        # Very low values should clamp to 0.0
        strength = calculate_signal_strength(
            speech_act_score=0.0,
            graduation_score=0.0,
            is_monogloss=False,
            hedging_penalty=1.0,
        )
        assert strength == 0.0

    def test_classify_signal_type(self):
        """Test signal type classification."""
        assert classify_signal_type(0.8) == "costly"
        assert classify_signal_type(0.5) == "neutral"
        assert classify_signal_type(0.2) == "cheap_talk"

    def test_hedging_penalty_impact(self):
        """Test that hedging penalty reduces signal strength."""
        base_strength = calculate_signal_strength(
            speech_act_score=0.8,
            graduation_score=0.5,
            is_monogloss=True,
            hedging_penalty=0.0,
        )
        hedged_strength = calculate_signal_strength(
            speech_act_score=0.8,
            graduation_score=0.5,
            is_monogloss=True,
            hedging_penalty=0.8,
        )
        assert hedged_strength < base_strength


class TestBayesianUpdateResult:
    """Tests for BayesianUpdateResult model."""

    def test_bayesian_update_result_immutable(self):
        """Test that BayesianUpdateResult is frozen."""
        result = BayesianUpdateResult(
            speaker_id="test",
            posterior_mean=0.5,
            posterior_mode=0.5,
            posterior_std=0.1,
            credible_interval_95=(0.3, 0.7),
            filter_type="kalman",
            signal_strength=0.8,
            ess=float("nan"),
        )
        with pytest.raises(Exception):  # FrozenModelError in Pydantic
            result.posterior_mean = 1.0

    def test_bayesian_update_result_fields(self):
        """Test all required fields are present."""
        result = BayesianUpdateResult(
            speaker_id="test",
            posterior_mean=0.5,
            posterior_mode=0.5,
            posterior_std=0.1,
            credible_interval_95=(0.3, 0.7),
            filter_type="particle",
            signal_strength=0.8,
            ess=500.0,
        )
        assert result.speaker_id == "test"
        assert result.filter_type == "particle"
        assert result.ess == 500.0
