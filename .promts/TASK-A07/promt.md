# TASK-A07 · BAYESIAN POSITION ESTIMATION — UPGRADED ENGINEERING REVIEW
## bb-paxdata · commit `8d37ef99` · Report Generated: 2026-06-05

---

## METADATA

```
Task ID          : TASK-A07
Task Name        : Bayesian Position Estimation — Morrow (1994) Signal Theory
Category         : Academy → Engineering Bridge
Difficulty       : XL (8–13 story points)
Priority         : P2 (non-critical path, high value)
Dependencies     : TASK-A04, TASK-A03, TASK-A01
Estimated Effort : 4–6 weeks (experienced developer)
Report Basis     : GRAPH_REPORT.md (8699 nodes, 15462 edges, commit 8d37ef99)
                   TASK-A07_DEVELOPMENT_REPORT.md v1.0 (2025-01-06)
Supersedes       : TASK-A07_DEVELOPMENT_REPORT.md v1.0
```

---

## SECTION 0 — CODEBASE STATE (GRAPH-DERIVED FACTS)

Graph extraction from commit `8d37ef99` exposes the following structural facts relevant to TASK-A07:

**God Nodes affecting integration scope:**

| Node | Edge Count | Communities Bridged |
|---|---|---|
| `Analysis` | 180 | 28+ |
| `Segment` | 122 | 31+ |
| `SpeechActClassification` | 71 | Multiple |
| `ServiceContainer` | 64 | Multiple |

Any modification to `ForecastResult`, `Analysis`, or `DKIAssembler` will propagate risk across these communities. Schema changes must be backward-compatible with `ConfigDict(frozen=True)` patterns enforced codebase-wide.

**Directly relevant communities:**

- **Community 109** — `ForecastResult`, `TimeSlice`, `ChangepointDetector`, `EWMA`, `RiskForecaster`; cohesion 0.20 (tight)
- **Community 584** — `PooleRosenthalPositionTracker`, `DynamicPositionTracker` protocol, `compute_velocity()`
- **Community 487** — `HedgingServiceProtocol`, `HedgingResult`, all application protocols
- **Community 8**  — Prior code-review findings including "1.3 Missing Protocol Definition Violates IoC Architecture" and "1.2 Frozen Pydantic Model Mutation Breaks Deserialization"
- **Community 223** — Major findings including missing `DynamicPositionTracker` protocol resolution
- **Community 473** — `AnomalyServiceProtocol`, `LODPResult`, `TokenizerServiceProtocol` — all concrete protocol definitions live here
- **Community 696** — `AnalysisPipeline`, `AppraisalServiceProtocol`, Phase 1/2 bypass logic; 105 nodes (high integration risk)

**Inferred edges to verify before implementation:**
- `Analysis` has 165 INFERRED edges (avg confidence 0.59); edges to `DKIAssembler` and `AnalysisAssembler` must be verified against actual source.
- `Segment` has 108 INFERRED edges; edges to `EpisodicThematicFeatures` and `AnalysisAssembler` require verification.

---

## SECTION 1 — THEORETICAL MODEL FIDELITY ASSESSMENT

### 1.1 Morrow (1994) Mapping

The original report maps signal cost onto likelihood noise via:

```
sigma = 0.5 * (1.0 - signal_strength) + 0.1  →  range [0.1, 0.6]
```

**Gap:** Morrow (1994) Chapter 8 establishes costly signaling credibility through sender cost structure, not through a linear noise parameter. The mapping `signal_cost → sigma` has no derivation in the report. The choice of linear interpolation over exponential decay (which matches the marginal credibility curve in Bayesian signaling games) is not justified.

**Gap:** The report conflates *signal cost* (a property of the sender's action) with *measurement noise* (a property of the observer's inference). In Bayesian Nash Equilibrium, the likelihood update `P(signal | θ)` is not the same as measurement noise `R` in a Kalman filter. The Kalman `R` matrix models sensor imprecision; Morrow's signal credibility models strategic information content. These are separate quantities that the proposed implementation conflates.

**Correct formulation:** The Morrow-consistent update is:

```python
# Morrow-faithful likelihood weight
def morrow_likelihood(observation: float, theta_particle: float,
                      signal_strength: float) -> float:
    """
    P(signal | theta) weighted by signal credibility.
    Costly signal: credibility = 1.0, uses narrow Gaussian.
    Cheap talk: credibility < 1.0, flattens the likelihood, reducing update.
    """
    credibility = signal_strength  # maps [0, 1] to [0, 1]
    baseline_sigma = 0.5           # uninformative prior width
    signal_sigma = 0.1             # minimum observation uncertainty
    # Effective sigma: credible signal → tight; cheap talk → broad
    effective_sigma = signal_sigma + baseline_sigma * (1.0 - credibility)
    # Weighted likelihood: costly signals fully update; cheap talk partially
    return credibility * norm.pdf(observation, loc=theta_particle,
                                  scale=effective_sigma)
```

This formulation keeps cheap talk in the likelihood (it is not ignored) but reduces its update weight, consistent with Morrow's equilibrium conditions.

### 1.2 SBI Scale vs. θ Domain

The report states θ ∈ [-3, +3] (SBI scale). The Kalman filter is initialized with:

```python
self.kf.x = np.array([[0.0]])  # Initial position
self.kf.P = np.array([[1.0]])  # Initial covariance
```

A `P` of 1.0 on a [-3, +3] domain implies approximately 68% of the prior mass falls within [-1, +1]. This is acceptable only if 0.0 is a theoretically motivated neutral position. For a new speaker with no prior observations, initial `P` should be `3.0` to represent a uniform-equivalent prior over the full domain. The process noise `Q = 0.1` implies a standard deviation of ~0.32 per time step, reasonable for intra-session tracking but under-dispersed for inter-session gaps. The original report notes this but does not provide a formula for gap-adjusted `Q`.

**Proposed gap-adjusted process noise:**

```python
def adjusted_process_noise(base_q: float, delta_days: float,
                            session_rate: float = 1.0) -> float:
    """
    Scale process noise by temporal gap between observations.
    session_rate: expected sessions per day (calibration parameter).
    """
    # Larger gap → more uncertainty about position drift
    return base_q * (1.0 + delta_days / (1.0 / session_rate))
```

---

## SECTION 2 — CRITICAL FINDINGS

---

### FINDING C-01: GaussianDistribution Dataclass — Method/Attribute Name Collision

**Classification:** CRITICAL
**Location:** `src/bb_paxdata/domain/services/bayesian_position_tracker.py` — `GaussianDistribution` dataclass

**Root Cause:**

The proposed `GaussianDistribution` dataclass defines `mean: float` and `std: float` as fields AND declares methods named `mean()` and `std()`. In Python `@dataclass`, field names take precedence in `__init__` generation; however, class-level method definitions override the instance attribute binding. The result is that `self.mean` resolves to the *bound method*, not the float field, causing `mean()` to recurse infinitely and `credible_interval()` to produce a `TypeError`.

```python
# AS PROPOSED (broken):
@dataclass
class GaussianDistribution(Distribution):
    mean: float   # field
    std: float    # field

    def mean(self) -> float:      # shadows the field — recurses
        return self.mean

    def std(self) -> float:       # shadows the field — recurses
        return self.std
```

Python raises `RecursionError` at runtime on any call to `GaussianDistribution.mean()`.

**Proposed Resolution:**

Use distinct field names and override the abstract protocol methods to return them:

```python
@dataclass(frozen=True)
class GaussianDistribution(Distribution):
    mu: float       # renamed to avoid collision
    sigma: float    # renamed to avoid collision

    def mode(self) -> float:
        return self.mu

    def mean(self) -> float:
        return self.mu

    def std(self) -> float:
        return self.sigma

    def credible_interval(self, alpha: float = 0.05) -> tuple[float, float]:
        from scipy.stats import norm as _norm
        z = _norm.ppf(1.0 - alpha / 2.0)
        return (self.mu - z * self.sigma, self.mu + z * self.sigma)
```

The `Distribution` base class (`abstract` ABC, not `@dataclass`) must define `mean()`, `std()`, `mode()`, `credible_interval()` as `@abstractmethod`, not as dataclass fields.

**Impact Assessment:** Any instantiation of `GaussianDistribution` that calls `.mean()`, `.std()`, or `.credible_interval()` will raise `RecursionError` at runtime. The Kalman filter posterior path (`_update_kalman`) depends on `GaussianDistribution` as its posterior container. This failure is not detectable at import time; it will surface only at first Bayesian update execution.

---

### FINDING C-02: `filterpy` Incompatibility with numpy >= 1.24

**Classification:** CRITICAL
**Location:** `pyproject.toml`, `src/bb_paxdata/domain/services/bayesian_position_tracker.py` — `KalmanPositionTracker.__init__`

**Root Cause:**

`filterpy 1.4.5` (2018, last release) uses deprecated numpy attributes (`np.float`, `np.int`, `np.complex`) removed in numpy 1.24. The graph confirms the project already requires `numpy >= 1.24` (Community 570 `WordfishScaler` uses numpy 1.24+ array typing; Community 182 `BootstrapSignificanceTester` uses `np.float64`). Installing `filterpy 1.4.5` against the existing numpy version will raise `AttributeError: module 'numpy' has no attribute 'float'` at `from filterpy.kalman import KalmanFilter`.

**Verification:**

```bash
python -c "import numpy; print(numpy.__version__)"  # Will be >= 1.24
pip install filterpy==1.4.5
python -c "from filterpy.kalman import KalmanFilter"
# AttributeError: module 'numpy' has no attribute 'float'
```

**Proposed Resolution:**

Replace `filterpy` with a self-contained Kalman implementation using only `numpy` and `scipy`, eliminating the unmaintained dependency:

```python
import numpy as np
from dataclasses import dataclass, field

@dataclass
class KalmanState:
    x: np.ndarray   # State vector (dim_x, 1)
    P: np.ndarray   # State covariance (dim_x, dim_x)
    F: np.ndarray   # State transition (dim_x, dim_x)
    H: np.ndarray   # Measurement matrix (dim_z, dim_x)
    Q: np.ndarray   # Process noise (dim_x, dim_x)
    R: np.ndarray   # Measurement noise (dim_z, dim_z)

class KalmanPositionTracker:
    """
    1-D Kalman filter for position tracking. No external dependencies.
    Implements standard predict-update cycle.
    """
    def __init__(self, process_noise: float = 0.1,
                 measurement_noise: float = 0.5,
                 initial_position: float = 0.0,
                 initial_covariance: float = 3.0) -> None:
        self._state = KalmanState(
            x=np.array([[initial_position]], dtype=np.float64),
            P=np.array([[initial_covariance]], dtype=np.float64),
            F=np.array([[1.0]], dtype=np.float64),
            H=np.array([[1.0]], dtype=np.float64),
            Q=np.array([[process_noise]], dtype=np.float64),
            R=np.array([[measurement_noise]], dtype=np.float64),
        )

    def predict(self, delta_t_days: float = 1.0,
                base_process_noise: float | None = None) -> None:
        """Predict step with optional time-gap-adjusted Q."""
        s = self._state
        if base_process_noise is not None:
            adjusted_q = base_process_noise * (1.0 + delta_t_days)
            s.Q[0, 0] = adjusted_q
        s.x = s.F @ s.x
        s.P = s.F @ s.P @ s.F.T + s.Q

    def update(self, observation: float,
               measurement_noise: float | None = None) -> tuple[float, float]:
        """
        Update step. Returns (posterior_mean, posterior_std).
        measurement_noise: override R for this step (e.g. from UncertaintyScorer).
        """
        s = self._state
        if measurement_noise is not None:
            s.R[0, 0] = max(measurement_noise, 1e-6)  # avoid singular R
        # Innovation
        y = np.array([[observation]]) - s.H @ s.x
        S = s.H @ s.P @ s.H.T + s.R
        K = s.P @ s.H.T @ np.linalg.inv(S)
        s.x = s.x + K @ y
        s.P = (np.eye(1) - K @ s.H) @ s.P
        # Symmetrize to prevent numerical drift
        s.P = (s.P + s.P.T) / 2.0
        return float(s.x[0, 0]), float(np.sqrt(max(s.P[0, 0], 0.0)))

    @property
    def posterior_mean(self) -> float:
        return float(self._state.x[0, 0])

    @property
    def posterior_variance(self) -> float:
        return float(self._state.P[0, 0])
```

Remove `filterpy` from `pyproject.toml`. No external Kalman library is required for the 1-D case.

**Impact Assessment:** With `filterpy` in `pyproject.toml` and `numpy >= 1.24` already installed, `poetry install` will succeed (filterpy installs) but any import of `KalmanFilter` will crash the worker at runtime. This is a deployment blocker. All Kalman-based paths will be inoperative.

---

### FINDING C-03: `_update_kalman()` and `_update_particle()` Are Unimplemented Stubs

**Classification:** CRITICAL
**Location:** `src/bb_paxdata/domain/services/bayesian_position_tracker.py` — `BayesianPositionTracker._update_kalman()`, `BayesianPositionTracker._update_particle()`

**Root Cause:**

Both methods contain only `pass` and return `None` implicitly. The `update()` dispatch method calls them and returns their result:

```python
def update(self, observation: float, signal_strength: float,
           uncertainty: float = 0.5) -> BayesianPositionTracker:
    if self.filter_type == "kalman":
        return self._update_kalman(observation, uncertainty)   # returns None
    else:
        return self._update_particle(observation, signal_strength)  # returns None
```

Any caller assigning the result to a variable (as the `DKIAssembler` integration code does: `self._bayesian_tracker = self._bayesian_tracker.update(...)`) will silently replace the tracker with `None`, causing `AttributeError` on the next access.

**Proposed Resolution:**

The `BayesianPositionTracker` dataclass pattern is architecturally incorrect for this use case. The tracker's state (particles or Kalman state) is mutable across calls; a frozen-immutable dataclass cannot own it. The correct pattern is a stateful tracker class that holds its own filter internals and returns updated statistics:

```python
@dataclass
class BayesianUpdateResult:
    """Immutable snapshot of posterior state after one update."""
    speaker_id: str
    posterior_mean: float
    posterior_mode: float
    posterior_std: float
    credible_interval_95: tuple[float, float]
    filter_type: Literal["kalman", "particle"]
    signal_strength: float
    ess: float  # Effective Sample Size (particle filter only; NaN for Kalman)

class BayesianPositionTracker:
    """
    Stateful Bayesian position tracker. Not frozen; owns filter internals.
    Thread-safe only within a single speaker context (not shared across speakers).
    """
    def __init__(self, speaker_id: str,
                 filter_type: Literal["kalman", "particle"] = "particle",
                 particle_count: int = 1000,
                 prior_mean: float = 0.0,
                 prior_std: float = 3.0,
                 process_noise: float = 0.1) -> None:
        self.speaker_id = speaker_id
        self.filter_type = filter_type
        if filter_type == "kalman":
            self._kalman = KalmanPositionTracker(
                process_noise=process_noise,
                initial_covariance=prior_std ** 2,
                initial_position=prior_mean,
            )
            self._pf: ParticleFilterPositionTracker | None = None
        else:
            self._kalman = None
            self._pf = ParticleFilterPositionTracker(
                particle_count=particle_count,
                prior_mean=prior_mean,
                prior_std=prior_std,
                process_noise=process_noise,
            )

    def update(self, observation: float, signal_strength: float,
               measurement_noise: float = 0.5,
               delta_t_days: float = 1.0) -> BayesianUpdateResult:
        if self.filter_type == "kalman":
            assert self._kalman is not None
            self._kalman.predict(delta_t_days=delta_t_days)
            mean, std = self._kalman.update(
                observation, measurement_noise=measurement_noise
            )
            z = 1.959963985  # norm.ppf(0.975)
            ci = (mean - z * std, mean + z * std)
            return BayesianUpdateResult(
                speaker_id=self.speaker_id,
                posterior_mean=mean,
                posterior_mode=mean,
                posterior_std=std,
                credible_interval_95=ci,
                filter_type="kalman",
                signal_strength=signal_strength,
                ess=float("nan"),
            )
        else:
            assert self._pf is not None
            self._pf.predict()
            self._pf.update(observation, signal_strength)
            mode, mean, ci = self._pf.get_posterior()
            std = self._pf.get_posterior_std()
            ess = self._pf.effective_sample_size()
            return BayesianUpdateResult(
                speaker_id=self.speaker_id,
                posterior_mean=mean,
                posterior_mode=mode,
                posterior_std=std,
                credible_interval_95=ci,
                filter_type="particle",
                signal_strength=signal_strength,
                ess=ess,
            )
```

**Impact Assessment:** Without implementation, `update()` returns `None` silently. The `DKIAssembler` integration code will replace `self._bayesian_tracker` with `None` on the first call, crashing all subsequent calls with `AttributeError: 'NoneType' object has no attribute 'update'`. This is a complete functional failure with no exception raised at the point of error.

---

### FINDING C-04: `_bayesian_trackers` Dict Is Not Thread-Safe

**Classification:** CRITICAL
**Location:** `src/bb_paxdata/domain/services/forecasting.py` — `RiskForecaster.__init__`, `RiskForecaster.forecast_next_panel_risk()`

**Root Cause:**

The original report proposes:

```python
self._bayesian_trackers: dict[str, BayesianPositionTracker] = {}
```

The graph (Community 514, Community 131, Community 38) confirms `_process_single_file()` is called concurrently and is one of the highest-degree nodes (87 edges). `RiskForecaster` instances are shared across concurrent pipeline workers via `ServiceContainer` singleton (Community 13, Community 489 confirms singleton pattern). Concurrent reads/writes to a plain `dict` in CPython are NOT thread-safe for structural mutations (key insertion, deletion). The `dict.get()` then `dict.__setitem__` pattern (read-check-write) is a race condition even under the GIL when IO-bound coroutines yield between steps.

**Proposed Resolution:**

Use a `threading.Lock` or restructure tracker ownership out of `RiskForecaster`:

```python
import threading
from typing import Final

class RiskForecaster:
    def __init__(self, ..., use_bayesian: bool = False,
                 filter_type: Literal["kalman", "particle"] = "particle") -> None:
        # ... existing fields ...
        self._use_bayesian: Final[bool] = use_bayesian
        self._filter_type: Final[Literal["kalman", "particle"]] = filter_type
        self._bayesian_trackers: dict[str, BayesianPositionTracker] = {}
        self._trackers_lock = threading.Lock()

    def _get_or_create_tracker(self, speaker_id: str) -> BayesianPositionTracker:
        """Thread-safe retrieval or creation of per-speaker tracker."""
        with self._trackers_lock:
            if speaker_id not in self._bayesian_trackers:
                self._bayesian_trackers[speaker_id] = BayesianPositionTracker(
                    speaker_id=speaker_id,
                    filter_type=self._filter_type,
                    prior_mean=0.0,
                    prior_std=3.0,
                )
            return self._bayesian_trackers[speaker_id]
```

**Note on architectural fit:** Storing per-speaker mutable state on a `ServiceContainer`-managed singleton creates a cross-request statefulness problem. A cleaner resolution is to move `BayesianPositionTracker` instantiation into the `DKIAssembler` (per-analysis-run lifetime) rather than `RiskForecaster` (application lifetime). See FINDING M-04 for the `RiskForecaster`/`TimeSlice` mismatch that makes this the only viable path anyway.

**Impact Assessment:** Under concurrent file processing (the documented production mode), two workers processing different speakers may simultaneously attempt to insert into `_bayesian_trackers`, causing dict corruption or lost updates. The `with self._trackers_lock` pattern is required immediately. Without it, particle state for speaker A may be overwritten by speaker B's first observation.

---

## SECTION 3 — MAJOR FINDINGS

---

### FINDING M-01: `EmpiricalDistribution.credible_interval()` Ignores Particle Weights

**Classification:** MAJOR
**Location:** `src/bb_paxdata/domain/services/bayesian_position_tracker.py` — `EmpiricalDistribution.credible_interval()`

**Root Cause:**

```python
def credible_interval(self, alpha: float = 0.05) -> tuple[float, float]:
    sorted_particles = np.sort(self.particles)
    n = len(self.particles)
    lower_idx = int(alpha / 2 * n)
    upper_idx = int((1 - alpha / 2) * n)
    return (float(sorted_particles[lower_idx]), float(sorted_particles[upper_idx]))
```

This method sorts `self.particles` and takes index-based quantiles, completely ignoring `self.weights`. This is correct only immediately after systematic resampling (when weights are uniform). However, `EmpiricalDistribution` is a standalone data container that may be constructed from particle states at any point in the filter lifecycle, including *before* resampling. Calling `credible_interval()` on a pre-resampling `EmpiricalDistribution` produces incorrect intervals. Furthermore, the `mean()` and `std()` methods on the same class *do* use `self.weights` via `np.average(..., weights=...)`, creating an internal inconsistency.

**Proposed Resolution:**

```python
def credible_interval(self, alpha: float = 0.05) -> tuple[float, float]:
    """
    Weighted quantile-based credible interval.
    Correct regardless of whether weights are uniform or not.
    """
    sorted_idx = np.argsort(self.particles)
    sorted_particles = self.particles[sorted_idx]
    sorted_weights = self.weights[sorted_idx]
    cumulative_weights = np.cumsum(sorted_weights)
    # Normalize (defensive)
    cumulative_weights /= cumulative_weights[-1]
    lower_idx = np.searchsorted(cumulative_weights, alpha / 2.0)
    upper_idx = np.searchsorted(cumulative_weights, 1.0 - alpha / 2.0)
    # Clip to valid range
    lower_idx = int(np.clip(lower_idx, 0, len(sorted_particles) - 1))
    upper_idx = int(np.clip(upper_idx, 0, len(sorted_particles) - 1))
    return (float(sorted_particles[lower_idx]), float(sorted_particles[upper_idx]))
```

**Impact Assessment:** Pre-resampling credible intervals will be miscalibrated, potentially severely so if the particle weight distribution is skewed. Downstream consumers comparing `credible_interval_95` against ground truth positions will observe coverage far below the target 0.90. The backtest success criterion (`CI coverage ≥ 0.90`) may fail specifically because of this defect.

---

### FINDING M-02: `signal_strength` Has No Source in `RiskForecaster.forecast_next_panel_risk()`

**Classification:** MAJOR
**Location:** `src/bb_paxdata/domain/models/forecast.py` — `ForecastResult.signal_strength`; `src/bb_paxdata/domain/services/forecasting.py` — `RiskForecaster.forecast_next_panel_risk()`

**Root Cause:**

The report adds `signal_strength: float` to `ForecastResult` and proposes the `RiskForecaster` populate it. However, `forecast_next_panel_risk()` takes `historical: Sequence[TimeSlice]` as its only data input. The `TimeSlice` model (Community 109) contains:

```python
# Community 109 members: ForecastResult, TimeSlice, ChangepointDetector, EWMA, RiskForecaster
# TimeSlice fields (from graph context):
# panel_id, timestamp, sentiment_delta, sentiment_volatility,
# keyness_index_deviation, computed_risk
```

There is no `speech_act`, `appraisal_vector`, `hedging_result`, or `signal_strength` in `TimeSlice`. `signal_strength` is computed from `SpeechActClassification`, `AppraisalVector`, and `HedgingResult` — none of which exist in the `RiskForecaster` context. The report acknowledges this implicitly by placing `signal_strength` computation in `DKIAssembler`, but then also adds it as a populated field to `ForecastResult` returned from `RiskForecaster`.

**Proposed Resolution:**

`ForecastResult.signal_strength` must not be populated by `RiskForecaster`. Two valid options:

Option A — Remove `signal_strength` from `ForecastResult`; it belongs to a `DKIResult` or `BayesianUpdateResult` layer, not the risk forecast layer.

Option B — Add `signal_strength: float = Field(default=float("nan"), ...)` with explicit documentation that `RiskForecaster` always produces `nan` for this field; only `DKIAssembler`-assembled results carry a meaningful value.

Option B is preferred for downstream compatibility:

```python
class ForecastResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    predicted_risk: float = Field(..., ge=0.0, le=10.0)
    trend: float
    volatility_forecast: float
    confidence_lower: float
    confidence_upper: float
    regime_stable: bool
    forecast_horizon_panels: int = 1
    # Bayesian extension fields — populated only when Bayesian path active
    credible_interval_95: tuple[float, float] = Field(default=(float("nan"), float("nan")))
    posterior_mode: float = Field(default=float("nan"))
    posterior_mean: float = Field(default=float("nan"))
    posterior_std: float = Field(default=float("nan"))
    filter_type: Literal["ewma", "kalman", "particle"] = "ewma"
    # signal_strength: NOT populated by RiskForecaster — belongs to DKIAssembler context
    # Consumers must check filter_type != "ewma" before using Bayesian fields.
```

**Impact Assessment:** If `signal_strength` is populated in `forecast_next_panel_risk()` with a hardcoded default (0.5 as the report suggests), it misrepresents data provenance. Downstream consumers treating this as an actual signal measurement will make incorrect inferences. If populated with `nan`, at least the invalidity is explicit.

---

### FINDING M-03: `engagement_boost` Weight Renders Contribution Negligibly Small

**Classification:** MAJOR
**Location:** `src/bb_paxdata/domain/services/bayesian_position_tracker.py` — `calculate_signal_strength()`

**Root Cause:**

```python
engagement_boost = 0.1 if appraisal.engagement_type == EngagementType.MONOGLOSS else -0.1

signal_strength = (
    0.5 * sa_score +
    0.3 * graduation_score +
    0.1 * engagement_boost -   # ← 0.1 * (±0.1) = ±0.01
    0.1 * hedging_penalty
)
```

`engagement_boost` is `±0.1`. Multiplied by the weight `0.1`, the actual contribution is `±0.01`. This means engagement type (MONOGLOSS vs. HETEROGLOSS) contributes at most 1 percentage point to signal strength — below any meaningful decision threshold. The weight effectively renders engagement irrelevant. Compare: `hedging_penalty` with weight `0.1` operates on `[0, 1]` → contributes `[0, 0.1]`, a 10x larger influence.

**Maximum achievable signal_strength analysis without this fix:**

```
DECLARATIVE + force_modifier + graduation=1.0 + MONOGLOSS + hedging=0.0:
  sa_score = 0.9 + 0.1 = 1.0 (clamped to effect of 0.5 * 1.0 = 0.5 in sum)
  graduation = 0.3 * 1.0 = 0.3
  engagement = 0.1 * 0.1 = 0.01
  hedging = -0.1 * 0.0 = 0.0
  total = 0.81 → clips to 0.81 (never reaches 1.0)
```

The "costly signal" threshold of 0.7 is reached only by DECLARATIVE + strong graduation + MONOGLOSS with minimal hedging. COMMISSIVE is capped at:

```
0.5 * 0.8 + 0.3 * 1.0 + 0.01 - 0 = 0.71
```

The threshold placement and weight assignment are internally consistent *given the mistaken engagement weight*, but the design intent (engagement matters) is violated.

**Proposed Resolution:**

Either apply `engagement_boost` directly (without the 0.1 multiplier), or set the engagement weight equal to the hedging weight:

```python
# Corrected formula — engagement contribution on par with hedging
SIGNAL_WEIGHTS = {
    "speech_act": 0.50,
    "graduation": 0.25,
    "engagement": 0.10,   # direct application of ±0.10
    "hedging": -0.15,     # increased penalty weight for stronger differentiation
}

signal_strength = (
    SIGNAL_WEIGHTS["speech_act"] * sa_score
    + SIGNAL_WEIGHTS["graduation"] * graduation_score
    + SIGNAL_WEIGHTS["engagement"] * (0.1 if is_monogloss else -0.1)
    + SIGNAL_WEIGHTS["hedging"] * hedging_penalty
)
# Note: sum clamps to [0, 1] via max/min
```

Weight rebalancing should be validated against expert-annotated signal strength ground truth (see Section 8.2 risk mitigation in original report).

**Impact Assessment:** The `classify_signal_type()` boundaries (`costly ≥ 0.7`, `cheap_talk ≤ 0.3`) were presumably calibrated with the engagement contribution in mind. With the current defect, signals that should be classified "costly" due to MONOGLOSS engagement may fall below 0.7. Particle filter measurement noise will be set too high for genuinely costly signals, degrading posterior convergence. The success criterion RMSE ≤ 0.72 is at risk.

---

### FINDING M-04: `BayesianPositionTracker` Does Not Implement `DynamicPositionTracker` Protocol — Repeated IoC Violation

**Classification:** MAJOR
**Location:** `src/bb_paxdata/application/pipeline/dki_assembler.py`; `src/bb_paxdata/application/protocols/__init__.py`

**Root Cause:**

The graph (Community 8, Finding 1.3: "Missing Protocol Definition Violates IoC Architecture") already documents this class of defect. The original report acknowledges the protocol mismatch and proposes a new parallel protocol `BayesianPositionTrackerProtocol`. This reproduces the anti-pattern: adding a concrete type as a direct dependency instead of extending or adapting the existing protocol.

The `DynamicPositionTracker` protocol requires:

```python
@runtime_checkable
class DynamicPositionTracker(Protocol):
    async def compute_velocity(
        self,
        trajectory: SpeakerTrajectory,
        smoothing_window: int = 3,
    ) -> DynamicPositionResult: ...
```

`BayesianPositionTracker.update()` is synchronous and operates on scalar observations, not `SpeakerTrajectory` objects. The conceptual mismatch is real, but the correct resolution is an adapter, not a parallel dependency.

**Proposed Resolution:**

Create `BayesianDynamicPositionAdapter` that implements `DynamicPositionTracker` and internally delegates to `BayesianPositionTracker`:

```python
class BayesianDynamicPositionAdapter:
    """
    Adapts BayesianPositionTracker to the DynamicPositionTracker protocol.
    Maintains per-speaker tracker state internally.
    Implements compute_velocity() by running Bayesian updates on trajectory points
    and computing velocity as the posterior mean derivative.
    """
    def __init__(self, filter_type: Literal["kalman", "particle"] = "particle",
                 particle_count: int = 1000,
                 process_noise: float = 0.1) -> None:
        self._trackers: dict[str, BayesianPositionTracker] = {}
        self._lock = threading.Lock()
        self._filter_type = filter_type
        self._particle_count = particle_count
        self._process_noise = process_noise

    async def compute_velocity(
        self,
        trajectory: SpeakerTrajectory,
        smoothing_window: int = 3,
    ) -> DynamicPositionResult:
        import asyncio
        # Run Bayesian updates in thread pool (CPU-bound particle ops)
        return await asyncio.get_event_loop().run_in_executor(
            None, self._compute_velocity_sync, trajectory, smoothing_window
        )

    def _compute_velocity_sync(
        self, trajectory: SpeakerTrajectory, smoothing_window: int
    ) -> DynamicPositionResult:
        with self._lock:
            tracker = self._trackers.setdefault(
                trajectory.speaker_id,
                BayesianPositionTracker(
                    speaker_id=trajectory.speaker_id,
                    filter_type=self._filter_type,
                    particle_count=self._particle_count,
                    process_noise=self._process_noise,
                )
            )
        posterior_means = []
        for pt in trajectory.positions:
            result = tracker.update(
                observation=pt.theta,
                signal_strength=getattr(pt, "signal_strength", 0.5),
                delta_t_days=getattr(pt, "delta_t_days", 1.0),
            )
            posterior_means.append(result.posterior_mean)
        # Velocity: finite difference on posterior means
        if len(posterior_means) >= 2:
            current_velocity = posterior_means[-1] - posterior_means[-2]
            acceleration = (
                (posterior_means[-1] - 2 * posterior_means[-2] + posterior_means[-3])
                if len(posterior_means) >= 3 else 0.0
            )
        else:
            current_velocity = 0.0
            acceleration = 0.0
        return DynamicPositionResult(
            speaker_id=trajectory.speaker_id,
            current_velocity=current_velocity,
            acceleration=acceleration,
            smoothed_positions=posterior_means,
        )
```

`DKIAssembler.__init__` then accepts `position_tracker: DynamicPositionTracker` as always, with `BayesianDynamicPositionAdapter` as the concrete implementation when Bayesian tracking is enabled. No new protocol needed. No IoC violation.

**Impact Assessment:** Introducing a parallel `BayesianPositionTrackerProtocol` that is never checked at runtime (no `@runtime_checkable`) means the type system provides no safety guarantee. The adapter pattern resolves both the IoC violation and the protocol conformance issue simultaneously while avoiding the `Optional[BayesianPositionTracker]` null-check proliferation in `DKIAssembler`.

---

### FINDING M-05: `HedgingResult` Constructed with Hardcoded Defaults in Integration Code

**Classification:** MAJOR
**Location:** `src/bb_paxdata/application/pipeline/dki_assembler.py` — `attach_dki()` Bayesian path

**Root Cause:**

The proposed integration code contains:

```python
hedging_result = HedgingResult(score=0.5, categories=[], confidence=0.5)
# Gerçek implementasyonda hedging result'ı Analysis'den çekin
```

The comment acknowledges the placeholder, but the `HedgingResult` with `score=0.5` is a neutral value that will classify every signal as "neutral" regardless of actual hedging content. This nullifies the Morrow-theoretic distinction between costly signals and cheap talk. If `HedgingResult` is not available on the `Analysis` object at the point `attach_dki()` is called, the Bayesian update is operating with degraded information.

**Root cause of availability:** The graph (Community 487) shows `HedgingServiceProtocol.analyze()` returns `HedgingResult`. The `CollectStage` runs hedging analysis. Whether `Analysis.hedging_result` is populated depends on the `CollectStage` output contract. The graph (Community 696) confirms `AnalysisPipeline` runs `CollectStage` before `DKIAssembler`. The `Analysis` domain model (Community 27, 180 edges) likely carries `hedging_result` already.

**Proposed Resolution:**

```python
# In DKIAssembler.attach_dki():
# Extract HedgingResult from Analysis — it should exist post-CollectStage
hedging_result: HedgingResult | None = getattr(analysis, "hedging_result", None)
if hedging_result is None:
    self._logger.warning(
        "hedging_result absent from Analysis; signal_strength will be degraded",
        speaker_id=speaker_id,
        segment_id=session_id,
    )
    # Fallback to neutral — clearly logged, not silently wrong
    hedging_result = HedgingResult(
        score=0.5, categories=[], confidence=0.0  # confidence=0 signals invalidity
    )

# Similarly for speech_act and appraisal_vector:
speech_act: SpeechActClassification | None = analysis.speech_act
appraisal: AppraisalVector | None = analysis.appraisal_vector

if speech_act is None or appraisal is None:
    signal_strength = 0.5  # neutral fallback
    self._logger.warning("speech_act or appraisal_vector absent; "
                         "defaulting signal_strength=0.5")
else:
    signal_strength = calculate_signal_strength(speech_act, appraisal, hedging_result)
```

**Impact Assessment:** With `score=0.5` hardcoded, all signals are classified "neutral" regardless of content. The particle filter will use `sigma = 0.5 * 0.5 + 0.1 = 0.35` uniformly. The RMSE improvement over EWMA will be minimal and will not reach the ≥ 10% target in the success criteria, causing a silent failure of the success criterion rather than a runtime error.

---

### FINDING M-06: `particles` Library Is Research-Grade and Python 3.12+ Incompatible

**Classification:** MAJOR
**Location:** `pyproject.toml` — proposed `particles = "^0.5.0"` dependency

**Root Cause:**

The `particles` library (nchopin/particles, version 0.5.0, 2023) is an academic Sequential Monte Carlo library. It has no SLA, no production maintenance guarantee, and its `setup.py`-based distribution is incompatible with `pyproject.toml`-native Poetry resolution in some configurations. More critically, it wraps its own resampling algorithms around `numpy` in ways that are incompatible with numpy's new `Generator` API (`numpy.random.Generator` vs. deprecated `numpy.random.RandomState`). The report proposes it as optional, but even optional dependencies create `poetry.lock` conflicts.

The self-contained `ParticleFilterPositionTracker` already present in the report fully covers the required functionality. The `particles` library provides no additional capability that justifies the dependency risk.

**Proposed Resolution:**

Remove `particles` from `pyproject.toml` entirely. The report's own `ParticleFilterPositionTracker` implementation (corrected per findings in this document) is sufficient. Only `scipy` (already a dependency per graph Community 570 `WordfishScaler`) and `numpy` are required.

Revised `pyproject.toml` additions:

```toml
[tool.poetry.dependencies]
# TASK-A07: No new top-level dependencies required.
# scipy and numpy are already present.
# filterpy REMOVED — replaced by self-contained KalmanPositionTracker.
# particles REMOVED — replaced by self-contained ParticleFilterPositionTracker.
```

**Impact Assessment:** Retaining `particles = "^0.5.0"` in `pyproject.toml` (even as optional) will cause `poetry lock` resolution conflicts against the existing scipy/numpy version constraints. Developers who run `poetry install --extras bayesian` will encounter incompatibility errors.

---

## SECTION 4 — MINOR FINDINGS

---

### FINDING m-01: Particle Filter Always Resamples — No ESS Gate

**Classification:** MINOR
**Location:** `src/bb_paxdata/domain/services/bayesian_position_tracker.py` — `ParticleFilterPositionTracker.update()`

**Root Cause:**

The `update()` method unconditionally calls `self._resample()` after every likelihood update. This is the naive approach and causes unnecessary diversity loss when the weight distribution is already near-uniform (i.e., when the observation is not very informative). Standard practice is to resample only when Effective Sample Size (ESS) falls below a threshold (typically N/2):

```python
def effective_sample_size(self) -> float:
    """
    ESS = 1 / sum(w_i^2). Range: [1, N].
    Low ESS (< N/2) indicates weight degeneracy; trigger resampling.
    """
    return float(1.0 / np.sum(self.weights ** 2))
```

**Proposed Resolution:**

```python
ESS_THRESHOLD_RATIO: float = 0.5  # Resample when ESS < N * threshold

def update(self, observation: float, signal_strength: float) -> None:
    sigma = 0.5 * (1.0 - signal_strength) + 0.1
    likelihood = norm.pdf(observation, loc=self.particles, scale=sigma)
    self.weights *= likelihood
    self.weights += 1e-300
    self.weights /= np.sum(self.weights)
    # Conditional resampling on ESS
    if self.effective_sample_size() < self.N * ESS_THRESHOLD_RATIO:
        self._resample()

def effective_sample_size(self) -> float:
    return float(1.0 / np.sum(self.weights ** 2))
```

**Impact Assessment:** Without ESS-gated resampling, each update step reduces particle diversity by forcing uniform weights. For a long sequence of weak signals (cheap talk), the particle cloud will converge prematurely. This inflates false confidence in the posterior and may cause the credible interval to narrow below its calibration target.

---

### FINDING m-02: `get_posterior()` KDE Fails on Degenerate Particle Cloud

**Classification:** MINOR
**Location:** `src/bb_paxdata/domain/services/bayesian_position_tracker.py` — `ParticleFilterPositionTracker.get_posterior()`

**Root Cause:**

```python
kde = gaussian_kde(self.particles, weights=self.weights)
```

`scipy.stats.gaussian_kde` raises `numpy.linalg.LinAlgError: singular matrix` when all particles have collapsed to the same value (particle degeneracy). This occurs when the likelihood is very tight (signal_strength → 1.0, sigma → 0.1) and all particles are weighted identically to the single high-likelihood region.

**Proposed Resolution:**

```python
def get_posterior(self) -> tuple[float, float, tuple[float, float]]:
    mean = float(np.average(self.particles, weights=self.weights))
    weighted_var = float(np.average(
        (self.particles - mean) ** 2, weights=self.weights
    ))
    std = float(np.sqrt(max(weighted_var, 1e-10)))

    # KDE mode — with degeneracy guard
    particle_range = self.particles.max() - self.particles.min()
    if particle_range < 1e-8:
        # Degenerate: all particles at same location
        mode = mean
    else:
        try:
            kde = gaussian_kde(self.particles, weights=self.weights,
                               bw_method="silverman")
            x_grid = np.linspace(self.particles.min() - std,
                                 self.particles.max() + std, 1000)
            mode = float(x_grid[np.argmax(kde(x_grid))])
        except np.linalg.LinAlgError:
            mode = mean  # Fallback to mean on singular KDE

    # Weighted quantile CI (uses corrected EmpiricalDistribution logic)
    ci = _weighted_quantile(self.particles, self.weights, [0.025, 0.975])
    return mode, mean, (float(ci[0]), float(ci[1]))

def get_posterior_std(self) -> float:
    mean = float(np.average(self.particles, weights=self.weights))
    return float(np.sqrt(max(
        float(np.average((self.particles - mean) ** 2, weights=self.weights)),
        1e-10
    )))
```

**Impact Assessment:** In production, a very decisive diplomatic statement (high signal strength) that causes particle collapse will crash the tracker with an unhandled `LinAlgError`. The exception propagates out of `attach_dki()` and, per the existing exception handling pattern, will be caught by the `except Exception as e: self._logger.warning(...)` block, silently falling back to EWMA. This means the most informative signals (costly signals, per Morrow theory) will cause the Bayesian path to fail and revert — the exact opposite of desired behavior.

---

### FINDING m-03: Bimodal Detection Test is Unreliable

**Classification:** MINOR
**Location:** `tests/unit/domain/services/test_bayesian_position_tracker.py` — `test_bimodal_detection()`

**Root Cause:**

```python
for _ in range(5):
    tracker.predict()
    tracker.update(1.0, signal_strength=0.8)

for _ in range(5):
    tracker.predict()
    tracker.update(-1.0, signal_strength=0.8)
```

With N=1000 particles and only 10 total updates, the particle filter will NOT reliably produce a bimodal posterior. The process noise (0.1 per step) will cause particles to diffuse after each predict step, and 5 updates toward +1.0 followed by 5 toward -1.0 will more likely produce a broad unimodal posterior centered near 0.0 than a bimodal one. A bimodal posterior requires the particle cloud to split and maintain two distinct modes, which requires the modes to be sufficiently separated relative to both process noise and measurement sigma.

**Proposed Resolution:**

Construct bimodality with a synthetic two-component particle initialization and verify it is maintained, rather than attempting to create it through sequential updates:

```python
def test_bimodal_detection():
    """Test bimodal posterior detection using synthetic bimodal initialization."""
    tracker = ParticleFilterPositionTracker(particle_count=2000)
    # Force bimodal initialization: 50% around +1.5, 50% around -1.5
    n_half = 1000
    tracker.particles = np.concatenate([
        np.random.normal(1.5, 0.2, n_half),
        np.random.normal(-1.5, 0.2, n_half),
    ])
    tracker.weights = np.ones(2000) / 2000

    # Single update with neutral observation should preserve bimodality
    tracker.update(observation=0.0, signal_strength=0.1)  # weak signal
    assert is_bimodal(tracker.particles, tracker.weights), (
        "Bimodal posterior should survive weak neutral signal update"
    )
```

**Impact Assessment:** A test that cannot reliably assert bimodality provides no coverage guarantee. The `is_bimodal()` function itself (using `find_peaks` with `height=np.max(density) * 0.5`) will return `False` on the proposed test input under normal process noise conditions, causing the test to intermittently fail or — worse — intermittently pass by chance, masking a defect.

---

### FINDING m-04: `backtest_jcpoa()` Declared Async With No Await Operations

**Classification:** MINOR
**Location:** `scripts/backtest_bayesian_tracker.py` — `backtest_jcpoa()`

**Root Cause:**

```python
async def backtest_jcpoa():
    data_path = Path("data/backtest/jcpoa_transcripts.json")
    with open(data_path) as f:              # synchronous IO
        transcripts = json.load(f)          # synchronous
    tracker = ParticleFilterPositionTracker(...)
    for transcript in transcripts:
        tracker.predict()                   # synchronous
        tracker.update(...)                 # synchronous
    # ... all synchronous operations
```

No `await` expression exists in the function body. `asyncio.run(backtest_jcpoa())` will schedule the coroutine and complete it synchronously in one event loop tick. The `async def` declaration is misleading and the `@pytest.mark.asyncio` test decorator adds unnecessary event loop overhead.

**Proposed Resolution:**

```python
# Remove async/await entirely:
def backtest_jcpoa() -> tuple[float, float]:
    """Synchronous backtest. Use threading for parallelism if needed."""
    ...

# Test:
def test_jcpoa_backtest():
    rmse, coverage = backtest_jcpoa()
    assert rmse <= 0.72
    assert coverage >= 0.90
```

**Impact Assessment:** Low. The functional behavior is identical. However, the misleading `async def` may cause future developers to add coroutine-based calls (e.g., awaiting database queries) that block the event loop from within what they believe is an async-safe context.

---

### FINDING m-05: `sigma` Mapping Has No Theoretical Basis in Morrow (1994)

**Classification:** MINOR
**Location:** `src/bb_paxdata/domain/services/bayesian_position_tracker.py` — `ParticleFilterPositionTracker.update()`

**Root Cause:**

```python
sigma = 0.5 * (1.0 - signal_strength) + 0.1  # range [0.1, 0.6]
```

This linear mapping from signal strength to measurement noise is not derived from Morrow (1994) nor from any standard Bayesian signaling framework. Morrow's model specifies *equilibrium conditions* under which costly signals are credible; it does not prescribe a measurement noise schedule. The choice of [0.1, 0.6] range and linear interpolation are arbitrary engineering decisions presented in the original report as theoretically motivated.

**Documentation Requirement** (not a code change):

The implementation comment must be explicit:

```python
# IMPLEMENTATION NOTE: The sigma schedule below is a heuristic engineering
# approximation, NOT derived from Morrow (1994). Morrow establishes that
# costly signals update beliefs more strongly; we approximate this by
# reducing measurement noise (sigma) for high-strength signals.
# The specific range [0.1, 0.6] and linear schedule require calibration
# against ground-truth annotation data. See TASK-A07 backtest criteria.
sigma = 0.5 * (1.0 - signal_strength) + 0.1
```

**Impact Assessment:** If future developers attempt to validate the implementation against Morrow (1994) and find no sigma schedule there, they may incorrectly conclude the implementation is wrong and remove the noise schedule entirely. Explicit documentation prevents this.

---

## SECTION 5 — INFORMATIONAL FINDINGS

---

### FINDING I-01: Prior Initialization Strategy for New vs. Returning Speakers Is Undefined

**Classification:** INFORMATIONAL
**Location:** `src/bb_paxdata/domain/services/bayesian_position_tracker.py` — `ParticleFilterPositionTracker.__init__()`

The report uses `prior_mean=0.0, prior_std=1.0` for all speakers unconditionally. Two cases require differentiated prior initialization:

Case A — *New speaker* (no historical data): Use uninformative prior `prior_std=3.0` (covers full SBI domain [-3,+3] at 1σ).

Case B — *Returning speaker* (historical data in DB): Use empirical mean and std from previous session as informative prior to achieve faster posterior convergence.

**Proposed Resolution:**

```python
async def load_speaker_prior(speaker_id: str,
                              analysis_repo: AnalysisRepository) -> tuple[float, float]:
    """
    Load prior from DB for returning speaker; use uninformative prior for new speaker.
    Returns (prior_mean, prior_std).
    """
    history = await analysis_repo.get_sbi_history(speaker_id, limit=20)
    if not history:
        return 0.0, 3.0  # Uninformative
    values = [h.sbi for h in history]
    return float(np.mean(values)), max(float(np.std(values)), 0.5)
```

---

### FINDING I-02: No `speaker_id` in `TimeSlice` — `RiskForecaster` Bayesian Path Cannot Isolate Per-Speaker State

**Classification:** INFORMATIONAL
**Location:** `src/bb_paxdata/domain/services/forecasting.py` — `RiskForecaster.forecast_next_panel_risk()`

`TimeSlice` (Community 109) does not carry `speaker_id`. `forecast_next_panel_risk()` aggregates panel-level risk from a sequence of `TimeSlice` objects. The Bayesian tracker requires per-speaker particle state. The `_bayesian_trackers: dict[str, BayesianPositionTracker]` dict assumes `speaker_id` is available in the `RiskForecaster` context, but the method signature `forecast_next_panel_risk(historical: Sequence[TimeSlice])` provides no speaker identity.

**Consequence:** The `RiskForecaster` Bayesian path is architecturally orphaned — it cannot function as designed without either (a) modifying `TimeSlice` to carry `speaker_id`, or (b) accepting `speaker_id` as a parameter to `forecast_next_panel_risk()`. Option (b) is a breaking interface change. The correct resolution is to place Bayesian tracking in `DKIAssembler` (which operates at speaker-segment granularity) and not in `RiskForecaster` (which operates at panel granularity). This aligns with FINDING M-02.

---

### FINDING I-03: `ForecastResult` Frozen Model — `credible_interval_95: tuple[float, float]` Requires Pydantic v2 Serialization Handling

**Classification:** INFORMATIONAL
**Location:** `src/bb_paxdata/domain/models/forecast.py` — `ForecastResult`

Pydantic v2 with `ConfigDict(frozen=True)` serializes `tuple[float, float]` correctly to JSON, but SQLAlchemy ORM models that store `ForecastResult` fields may require explicit column type annotations. The graph (Community 8, Finding "1.2 Frozen Pydantic Model Mutation Breaks Deserialization") documents an existing defect class around frozen model deserialization.

If `credible_interval_95` is stored as a JSON column in the ORM, ensure:

```python
# In ORM model (e.g., ForecastResultModel):
credible_interval_95: Mapped[str] = mapped_column(
    JSON, nullable=True,
    comment="Serialized tuple[float, float] for Bayesian 95% CI"
)
```

And add a deserialization validator:

```python
@field_validator("credible_interval_95", mode="before")
@classmethod
def parse_ci_from_json(cls, v: Any) -> tuple[float, float]:
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return (float(v[0]), float(v[1]))
    if isinstance(v, str):
        import json as _json
        parsed = _json.loads(v)
        return (float(parsed[0]), float(parsed[1]))
    return (float("nan"), float("nan"))
```

---

## SECTION 6 — CORRECTED IMPLEMENTATION SPECIFICATION

### 6.1 Revised Dependency Manifest

```toml
# pyproject.toml — TASK-A07 additions
[tool.poetry.dependencies]
# No new dependencies required.
# scipy >= 1.13 — already present (WordfishScaler, AggregationEngine)
# numpy >= 1.24 — already present
# filterpy — DO NOT ADD (numpy 1.24+ incompatible)
# particles — DO NOT ADD (research-grade, dependency conflict risk)
```

### 6.2 Corrected New File Manifest

```
src/bb_paxdata/domain/services/bayesian_position_tracker.py  [NEW — fully implemented]
  Classes:
    KalmanState                    — frozen dataclass for Kalman filter state
    KalmanPositionTracker          — self-contained 1-D Kalman (no filterpy)
    ParticleFilterPositionTracker  — ESS-gated, weight-aware, degeneracy-safe
    BayesianUpdateResult           — frozen dataclass for immutable update snapshot
    BayesianPositionTracker        — stateful wrapper, thread-safe per speaker
    BayesianDynamicPositionAdapter — DynamicPositionTracker protocol adapter
  Functions:
    calculate_signal_strength()    — corrected weight formula
    classify_signal_type()         — unchanged
    _weighted_quantile()           — internal utility for weight-aware CI

src/bb_paxdata/domain/models/bayesian_models.py              [NEW — optional]
  Classes:
    Distribution                   — ABC (not dataclass), abstract interface
    GaussianDistribution           — frozen dataclass, mu/sigma fields
    EmpiricalDistribution          — weight-aware quantile methods

scripts/backtest_bayesian_tracker.py                         [NEW — synchronous]
  Functions:
    backtest_jcpoa() -> tuple[float, float]   — synchronous (not async)
    backtest_minsk() -> tuple[float, float]
    is_bimodal(particles, weights) -> bool
```

### 6.3 Revised Updated File Manifest

```
src/bb_paxdata/application/pipeline/dki_assembler.py
  Change: Accept position_tracker: DynamicPositionTracker (unchanged interface)
  Change: BayesianDynamicPositionAdapter injected as position_tracker when
          use_bayesian=True (via config flag or DI container)
  Change: Extract HedgingResult from analysis object (not hardcoded default)
  Change: Log warning (not silent default) when speech_act/appraisal absent

src/bb_paxdata/domain/services/forecasting.py
  Change: Remove _bayesian_trackers dict and Bayesian logic entirely
  Rationale: RiskForecaster has no speaker_id context; Bayesian tracking
             belongs in DKIAssembler (see FINDING M-02, FINDING I-02)
  Change: Add thread-safety to existing mutable state if any shared

src/bb_paxdata/domain/models/forecast.py
  Change: Add Bayesian extension fields with default float("nan")
  Change: Add field_validator for credible_interval_95 deserialization
  Change: signal_strength field: default=float("nan"), documented as
          DKIAssembler-populated only (not RiskForecaster)

src/bb_paxdata/application/protocols/__init__.py
  No new protocols added. BayesianDynamicPositionAdapter implements
  the existing DynamicPositionTracker protocol.

pyproject.toml
  No additions. filterpy and particles explicitly not added.
```

---

## SECTION 7 — REVISED SUCCESS CRITERIA

Original success criteria are preserved with the following amendments:

### 7.1 Kalman Filter RMSE

```python
# Criterion unchanged: kalman_rmse <= ewma_rmse * 0.90
# Pre-condition: KalmanPositionTracker must use initial_covariance=prior_std**2,
# not the hardcoded P=[[1.0]] in the original report.
# Calibrate prior_std from SBI domain analysis before benchmarking.
```

### 7.2 Credible Interval Coverage

```python
# Criterion unchanged: coverage_rate >= 0.90
# Measurement must use corrected weighted-quantile CI (FINDING M-01).
# Coverage measured on pre-resampling EmpiricalDistribution will be incorrect.
```

### 7.3 Particle Filter Bimodal Detection

```python
# Criterion amended: bimodal_accuracy >= 0.70
# Test methodology: use synthetic bimodal initialization (FINDING m-03),
# not sequential conflicting updates.
# is_bimodal() peak detection threshold: np.max(density) * 0.5
# is_bimodal() minimum peak separation: > 0.5 * domain_width to exclude noise peaks
```

### 7.4 Pipeline Latency

```python
# Criterion unchanged: latency_increase < 0.20
# NOTE: Particle filter operations (particle_count=1000, N iterations) are
# CPU-bound. The latency measurement must run in the same async context as
# production (asyncio.get_event_loop().run_in_executor).
# Baseline measurement must be the DKIAssembler path, not RiskForecaster
# (since Bayesian tracking moves to DKIAssembler per this report).
```

---

## SECTION 8 — REVISED TEST STRATEGY

### 8.1 Unit Tests — Corrected Cases

```python
# tests/unit/domain/services/test_bayesian_position_tracker.py

def test_kalman_no_recursion_error():
    """Regression test for FINDING C-01: GaussianDistribution method collision."""
    dist = GaussianDistribution(mu=0.0, sigma=1.0)
    assert dist.mean() == 0.0      # Must not recurse
    assert dist.std() == 1.0       # Must not recurse
    ci = dist.credible_interval()
    assert ci[0] < 0.0 < ci[1]

def test_kalman_tracker_no_filterpy():
    """Regression test for FINDING C-02: filterpy removal."""
    import sys
    assert "filterpy" not in sys.modules, "filterpy must not be imported"
    tracker = KalmanPositionTracker()
    tracker.predict()
    mean, std = tracker.update(0.5, measurement_noise=0.3)
    assert isinstance(mean, float)
    assert isinstance(std, float)
    assert std < 3.0  # Should reduce from initial covariance

def test_particle_filter_ess_gated_resampling():
    """Verify ESS gate prevents premature resampling on weak signals."""
    tracker = ParticleFilterPositionTracker(particle_count=1000)
    initial_particle_variance = float(np.var(tracker.particles))
    tracker.update(observation=0.5, signal_strength=0.05)  # Very weak signal
    post_particle_variance = float(np.var(tracker.particles))
    # Weak signal: ESS should be high → no resampling → diversity preserved
    assert post_particle_variance > initial_particle_variance * 0.8, (
        "Weak signal update must preserve particle diversity via ESS gate"
    )

def test_empirical_distribution_weighted_ci():
    """Regression test for FINDING M-01: weight-aware credible interval."""
    particles = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    # Heavily weight the high-value particles
    weights = np.array([0.01, 0.01, 0.01, 0.01, 0.96])
    weights /= weights.sum()
    dist = EmpiricalDistribution(particles=particles, weights=weights)
    ci = dist.credible_interval(alpha=0.05)
    # CI should be near 4.0, not straddling 0-4 uniformly
    assert ci[0] > 2.0, "Weighted CI lower bound must reflect weight concentration"
    assert ci[1] <= 4.0

def test_signal_strength_engagement_contribution():
    """Regression test for FINDING M-03: engagement_boost weight."""
    # Identical setup except engagement type
    speech_act = SpeechActClassification(
        primary_type=SpeechActType.ASSERTIVE, confidence=0.8
    )
    appraisal_mono = AppraisalVector(
        graduation_force=0.5, engagement_type=EngagementType.MONOGLOSS
    )
    appraisal_hetero = AppraisalVector(
        graduation_force=0.5, engagement_type=EngagementType.HETEROGLOSS
    )
    hedging = HedgingResult(score=0.3, categories=[], confidence=0.8)

    strength_mono = calculate_signal_strength(speech_act, appraisal_mono, hedging)
    strength_hetero = calculate_signal_strength(speech_act, appraisal_hetero, hedging)

    diff = strength_mono - strength_hetero
    assert diff >= 0.05, (
        f"MONOGLOSS must score >= 0.05 higher than HETEROGLOSS; got {diff:.4f}. "
        "Check engagement_boost weight (must not be 0.1 * ±0.1)."
    )

def test_update_returns_bayesian_update_result():
    """Regression test for FINDING C-03: update() must not return None."""
    tracker = BayesianPositionTracker(
        speaker_id="test", filter_type="particle"
    )
    result = tracker.update(observation=0.5, signal_strength=0.7)
    assert result is not None, "update() returned None (stub not implemented)"
    assert isinstance(result, BayesianUpdateResult)
    assert isinstance(result.posterior_mean, float)
    assert not (result.credible_interval_95[0] is None)

def test_particle_filter_degenerate_recovery():
    """Regression test for FINDING m-02: KDE degeneracy handling."""
    tracker = ParticleFilterPositionTracker(particle_count=100)
    # Force all particles to single point
    tracker.particles = np.full(100, 1.5)
    tracker.weights = np.ones(100) / 100
    # Must not raise LinAlgError
    mode, mean, ci = tracker.get_posterior()
    assert mode == pytest.approx(1.5, abs=1e-6)
    assert mean == pytest.approx(1.5, abs=1e-6)
```

---

## SECTION 9 — DEPENDENCY CHAIN VERIFICATION

Upstream dependencies confirmed via graph:

| Dependency | Status | Evidence |
|---|---|---|
| TASK-A01 (SRL) | Not required for Phase 1 | SRL output improves speech act classification but is not gating |
| TASK-A03 (Appraisal) | READY | Community 177: `AppraisalService`, `AppraisalVector` present |
| TASK-A04 (Speech Act) | READY | Community 524: `SpeechActClassifierService` present |
| `HedgingResult` | READY | Community 487: `HedgingServiceProtocol`, `HedgingResult` present |
| `DynamicPositionTracker` | READY | Community 584: `PooleRosenthalPositionTracker` confirms protocol exists |
| `DKIAssembler` | PRESENT | Community 142: confirmed in graph, `attach_dki()` present |
| `ForecastResult` (frozen) | PRESENT | Community 109: confirmed, `ConfigDict(frozen=True)` |
| `TimeSlice` | PRESENT | Community 109: confirmed, no speaker_id field |
| `Analysis` (god node) | HIGH RISK | 180 edges; any field addition must use `default=` |

Downstream impact:

| Downstream Task | Impact | Required Action |
|---|---|---|
| TASK-E01 (Contrastive Analysis) | Low | `BayesianUpdateResult.posterior_mean` can feed `AnalysisDelta` |
| TASK-E02 (GAT) | Low | `posterior_mean` as node feature — additive, no breaking change |
| TASK-E05 (Consensus/Divergence Tracker) | Medium | Bayesian CI adds direct value to multi-party position matrix |

---

## SECTION 10 — IMPLEMENTATION SEQUENCE (REVISED)

```
Step 1 [No dependencies, immediately testable]:
  Create bayesian_models.py: Distribution ABC, GaussianDistribution (mu/sigma),
  EmpiricalDistribution (weight-aware CI).
  Tests: test_kalman_no_recursion_error, test_empirical_distribution_weighted_ci

Step 2 [Depends on Step 1]:
  Create KalmanPositionTracker (no filterpy).
  Tests: test_kalman_tracker_no_filterpy

Step 3 [Depends on Step 1]:
  Create ParticleFilterPositionTracker (ESS-gated, degeneracy-safe).
  Tests: test_particle_filter_ess_gated_resampling,
         test_particle_filter_degenerate_recovery

Step 4 [Depends on Step 2, Step 3]:
  Create BayesianUpdateResult, BayesianPositionTracker (stateful wrapper).
  Tests: test_update_returns_bayesian_update_result

Step 5 [Depends on Step 4]:
  Implement calculate_signal_strength() (corrected engagement weight).
  Tests: test_signal_strength_engagement_contribution,
         test_calculate_signal_strength (costly/cheap_talk cases)

Step 6 [Depends on Step 4; requires DynamicPositionTracker import]:
  Create BayesianDynamicPositionAdapter.
  Tests: DKIAssembler integration tests with adapter injected as position_tracker

Step 7 [Depends on Step 5, Step 6]:
  Modify DKIAssembler.attach_dki() to extract HedgingResult from Analysis,
  log warnings on absence, compute signal_strength from real data.

Step 8 [Depends on Step 7]:
  Modify ForecastResult: add Bayesian extension fields (default=nan),
  add field_validator for CI deserialization.
  DO NOT modify RiskForecaster to add Bayesian path (see FINDING I-02).

Step 9 [Depends on Step 3]:
  Create synchronous backtest scripts (remove async/await).
  Acquire backtest data or use Wordfish θ values as proxy ground truth.

Step 10 [Depends on Step 7, Step 8]:
  End-to-end integration tests: DKIAssembler + BayesianDynamicPositionAdapter.
  Performance benchmarks: latency delta vs. PooleRosenthalPositionTracker.
```

---

## APPENDIX A — KNOWN LIMITATIONS AND DEFERRED ITEMS

```
[L-01] Backtest data (JCPOA, Minsk, Brexit) with expert-annotated positions
       does not exist in the repository. Backtest success criteria cannot be
       validated until data acquisition is complete. Use Wordfish θ from
       existing transcripts as proxy (acknowledged approximation).

[L-02] The sigma schedule [0.1, 0.6] is heuristic. Calibration against
       annotated ground truth is deferred to post-implementation evaluation.

[L-03] Multi-dimensional θ (one dimension per policy axis) is deferred.
       Single-dimensional SBI θ is the Phase 1 scope.

[L-04] ESS_THRESHOLD_RATIO = 0.5 is a standard default; domain-specific
       optimal value requires empirical calibration (grid search).

[L-05] BayesianDynamicPositionAdapter._compute_velocity_sync() uses
       naive finite difference for velocity. Smoothed velocity (SMA over
       posterior means) is implemented in PooleRosenthalPositionTracker
       and should be ported here for comparability.
```

---

**Report Version:** 2.0
**Supersedes:** TASK-A07_DEVELOPMENT_REPORT.md v1.0 (2025-01-06)
**Graph Basis:** BB-PAXDATA commit `8d37ef99` (8699 nodes, 15462 edges)
**Findings Summary:** 4 CRITICAL · 6 MAJOR · 5 MINOR · 3 INFORMATIONAL