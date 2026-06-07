"""
SRL Pipeline Metrics Collection & Export

Integrates with Prometheus/Grafana stack for production monitoring.
Tracks:
- Inference latency distributions
- Cache hit rates
- Error rates by category
- Resource utilization (GPU memory, CPU)
- Quality metrics (frame density, confidence distribution)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from functools import wraps

# Optional: Prometheus client for metrics export
try:
    from prometheus_client import Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # No-op stubs if Prometheus not installed
    class Counter:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kw):
            return self

        def inc(self, amount=1):
            pass

        def __call__(self, *args, **kw):
            return self

    class Histogram:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kw):
            return self

        def observe(self, amount):
            pass

        def __call__(self, *args, **kw):
            return self

    class Gauge:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kw):
            return self

        def set(self, value):
            pass

        def __call__(self, *args, **kw):
            return self


@dataclass
class SRLMetricsCollector:
    """
    Centralized metrics collection for SRL pipeline operations.
    Thread-safe for concurrent access.
    """

    # === Counters ===
    requests_total: Counter = field(
        default_factory=lambda: Counter(
            "srl_requests_total", "Total SRL extraction requests", ["status", "method"]
        )
    )

    cache_hits: Counter = field(
        default_factory=lambda: Counter(
            "srl_cache_hits_total", "Total cache hits", ["type"]
        )
    )

    cache_misses: Counter = field(
        default_factory=lambda: Counter(
            "srl_cache_misses_total", "Total cache misses", ["type"]
        )
    )

    contradictions_detected: Counter = field(
        default_factory=lambda: Counter(
            "srl_contradictions_total",
            "Total contradictions detected by pattern",
            ["pattern_type"],
        )
    )

    # === Histograms ===
    inference_latency: Histogram = field(
        default_factory=lambda: Histogram(
            "srl_inference_latency_seconds",
            "Time spent in SRL model inference",
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )
    )

    frame_confidence_distribution: Histogram = field(
        default_factory=lambda: Histogram(
            "srl_frame_confidence",
            "Distribution of SRL frame confidence scores",
            buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0],
        )
    )

    # === Gauges ===
    current_cache_size: Gauge = field(
        default_factory=lambda: Gauge(
            "srl_cache_current_size", "Current number of entries in prediction cache"
        )
    )

    model_memory_usage_bytes: Gauge = field(
        default_factory=lambda: Gauge(
            "srl_model_memory_bytes", "Estimated GPU/CPU memory used by SRL model"
        )
    )

    circuit_breaker_state: Gauge = field(
        default_factory=lambda: Gauge(
            "srl_circuit_breaker_state",
            "Current circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)",
        )
    )

    # Internal state
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _latency_samples: list[float] = field(default_factory=list)

    def record_request(
        self,
        status: str = "success",
        method: str = "single",
        latency_sec: float = 0.0,
        cache_hit: bool = False,
        num_frames: int = 0,
        avg_confidence: float = 0.0,
    ) -> None:
        """Record metrics for a single request."""
        self.requests_total.labels(status=status, method=method).inc()

        if latency_sec > 0:
            self.inference_latency.observe(latency_sec)

        if cache_hit:
            self.cache_hits.labels(type="prediction").inc()
        else:
            self.cache_misses.labels(type="prediction").inc()

        if num_frames > 0 and avg_confidence > 0:
            self.frame_confidence_distribution.observe(avg_confidence)

    def record_contradiction(self, pattern_type: str) -> None:
        """Record a detected contradiction."""
        self.contradictions_detected.labels(pattern_type=pattern_type).inc()

    def update_cache_size(self, size: int) -> None:
        """Update cache size gauge."""
        self.current_cache_size.set(size)

    def update_circuit_breaker(self, state: str) -> None:
        """Update circuit breaker state gauge."""
        state_map = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}
        self.circuit_breaker_state.set(state_map.get(state, -1))

    def update_model_memory(self, bytes_used: int) -> None:
        """Update model memory usage gauge."""
        self.model_memory_usage_bytes.set(bytes_used)

    def get_summary(self) -> dict:
        """Return current metrics summary (for logging/debugging)."""
        return {
            "prometheus_available": PROMETHEUS_AVAILABLE,
            "note": "Install prometheus_client for full metrics export",
        }


# Global singleton
_metrics_collector: SRLMetricsCollector | None = None


def get_srl_metrics() -> SRLMetricsCollector:
    """Get or create global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = SRLMetricsCollector()
    return _metrics_collector


# Decorator for automatic metrics collection
def track_srl_metrics(func):
    """
    Decorator to automatically collect metrics on SRL functions.

    Usage:
        @track_srl_metrics
        def extract_from_text(self, text):
            ...
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        metrics = get_srl_metrics()
        start_time = time.perf_counter()
        status = "success"

        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            status = f"error:{type(e).__name__}"
            raise
        finally:
            latency = time.perf_counter() - start_time
            metrics.record_request(status=status, latency_sec=latency)

    return wrapper
