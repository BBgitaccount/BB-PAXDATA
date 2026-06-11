"""
MetricsCollector module for Prometheus integration.
Provides thread-safe prometheus metric collection and a singleton interface.
"""

import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
    )
    from prometheus_client import (
        start_http_server as _start_http_server,
    )

    _prometheus_available = True
else:
    try:
        from prometheus_client import (
            CollectorRegistry,
            Counter,
            Gauge,
            Histogram,
        )
        from prometheus_client import (
            start_http_server as _start_http_server,
        )

        _prometheus_available = True
    except ImportError:
        _prometheus_available = False

        # Dummy implementations for type hinting and no-op
        class CollectorRegistry:  # type: ignore
            pass

        class Counter:  # type: ignore
            def __init__(
                self, name: str, _documentation: str, *args: Any, **kwargs: Any
            ) -> None:
                pass

            def labels(self, **kwargs: Any) -> Any:
                return self

            def inc(self, _amount: float = 1) -> None:
                pass

        class Gauge:  # type: ignore
            def __init__(
                self, name: str, _documentation: str, *args: Any, **kwargs: Any
            ) -> None:
                pass

            def labels(self, **kwargs: Any) -> Any:
                return self

            def set(self, value: float) -> None:
                pass

            def inc(self, _amount: float = 1) -> None:
                pass

            def dec(self, _amount: float = 1) -> None:
                pass

        class Histogram:  # type: ignore
            def __init__(
                self, name: str, _documentation: str, *args: Any, **kwargs: Any
            ) -> None:
                pass

            def labels(self, **kwargs: Any) -> Any:
                return self

            def observe(self, _amount: float) -> None:
                pass


class MetricsCollector:
    """Thread-safe Prometheus metrics toplayıcı — BB-PAXDATA."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._registry = CollectorRegistry()

        self._ai_request_duration_seconds = Histogram(
            "ai_request_duration_seconds",
            "Her AI backend çağrısının süresini ölçer",
            ["backend", "model", "status"],
            registry=self._registry,
        )

        self._cache_operations_total = Counter(
            "cache_operations_total",
            "Cache hit/miss sayacı",
            ["cache_type", "operation", "result"],
            registry=self._registry,
        )

        self._batch_fallback_total = Counter(
            "batch_fallback_total",
            "Batch işlem bozulup tekli moda düştüğünde artır",
            ["backend", "reason"],
            registry=self._registry,
        )

        self._active_tasks = Gauge(
            "active_tasks",
            "Şu anda işlenen cümle/segment/talep sayısı",
            ["task_type"],
            registry=self._registry,
        )

        self._processed_records_total = Counter(
            "processed_records_total",
            "Toplam İşlenen Kayıt",
            ["task_type", "panel_id", "status"],
            registry=self._registry,
        )

        self._json_recovery_attempts_total = Counter(
            "json_recovery_attempts_total",
            "JSON Recovery Denemesi",
            ["level", "result"],
            registry=self._registry,
        )

        self._pipeline_stage_duration_seconds = Histogram(
            "pipeline_stage_duration_seconds",
            "Pipeline a\u015famalar\u0131n\u0131n \u00e7al\u0131\u015fma s\u00fcreleri (saniye)",
            ["stage_name", "status"],
            registry=self._registry,
        )

        self._pipeline_files_processed_total = Counter(
            "pipeline_files_processed_total",
            "Toplam i\u015flenen transkript dosyas\u0131",
            ["status"],  # "success" | "skip" | "error"
            registry=self._registry,
        )

        # TASK-E01 Comparison Engine Metrics
        self._comparison_delta_duration_seconds = Histogram(
            "comparison_delta_duration_seconds",
            "Time to compute delta (fetch + compute) for session comparison",
            registry=self._registry,
        )

        self._comparison_narrative_duration_seconds = Histogram(
            "comparison_narrative_duration_seconds",
            "Time to generate LLM narrative for session comparison",
            ["status"],  # "success" | "failed"
            registry=self._registry,
        )

        self._comparison_total_duration_seconds = Histogram(
            "comparison_total_duration_seconds",
            "Total API response time for session comparison",
            ["status"],  # "success" | "failed"
            registry=self._registry,
        )

        self._comparison_llm_requests_total = Counter(
            "comparison_llm_requests_total",
            "Number of LLM calls for comparison narratives",
            registry=self._registry,
        )

        self._comparison_llm_failures_total = Counter(
            "comparison_llm_failures_total",
            "Number of LLM failures for comparison narratives",
            registry=self._registry,
        )

        self._comparison_sessions_compared_total = Counter(
            "comparison_sessions_compared_total",
            "Number of session comparisons performed",
            ["status"],  # "success" | "failed"
            registry=self._registry,
        )

        self._comparison_significant_changes_detected_total = Counter(
            "comparison_significant_changes_detected_total",
            "Number of significant changes detected in comparisons",
            registry=self._registry,
        )

    def record_ai_request(
        self,
        backend: str,
        model: str,
        duration_seconds: float,
        status: str,
    ) -> None:
        """Record the duration and status of an AI backend request."""
        with self._lock:
            self._ai_request_duration_seconds.labels(
                backend=backend, model=model, status=status
            ).observe(duration_seconds)

    def record_cache_operation(
        self,
        cache_type: str,
        operation: str,
        result: str,
    ) -> None:
        """Record a cache operation (hit/miss)."""
        with self._lock:
            self._cache_operations_total.labels(
                cache_type=cache_type, operation=operation, result=result
            ).inc()

    def record_batch_fallback(
        self,
        backend: str,
        reason: str,
    ) -> None:
        """Record when batch processing falls back to single mode."""
        with self._lock:
            self._batch_fallback_total.labels(backend=backend, reason=reason).inc()

    def set_active_tasks(
        self,
        task_type: str,
        count: int,
    ) -> None:
        """Set the number of currently active tasks."""
        with self._lock:
            self._active_tasks.labels(task_type=task_type).set(count)

    def record_processed(
        self,
        task_type: str,
        panel_id: str,
        status: str,
    ) -> None:
        """Record a processed record with its status."""
        with self._lock:
            self._processed_records_total.labels(
                task_type=task_type, panel_id=panel_id, status=status
            ).inc()

    def record_json_recovery(
        self,
        level: str,
        result: str,
    ) -> None:
        """Record a JSON recovery attempt."""
        with self._lock:
            self._json_recovery_attempts_total.labels(level=level, result=result).inc()

    def record_stage_duration(
        self,
        stage_name: str,
        duration_seconds: float,
        status: str,
    ) -> None:
        """Record the wall-clock execution time of a named pipeline stage."""
        with self._lock:
            self._pipeline_stage_duration_seconds.labels(
                stage_name=stage_name, status=status
            ).observe(duration_seconds)

    def record_file_processed(self, status: str) -> None:
        """Increment the total-files-processed counter.

        Args:
            status: One of 'success', 'skip', or 'error'.
        """
        with self._lock:
            self._pipeline_files_processed_total.labels(status=status).inc()

    # TASK-E01 Comparison Engine Metric Recording Methods
    def record_comparison_delta_duration(self, duration_seconds: float) -> None:
        """Record delta computation duration."""
        with self._lock:
            self._comparison_delta_duration_seconds.observe(duration_seconds)

    def record_comparison_narrative_duration(
        self, duration_seconds: float, status: str
    ) -> None:
        """Record LLM narrative generation duration."""
        with self._lock:
            self._comparison_narrative_duration_seconds.labels(status=status).observe(
                duration_seconds
            )

    def record_comparison_total_duration(
        self, duration_seconds: float, status: str
    ) -> None:
        """Record total comparison API response duration."""
        with self._lock:
            self._comparison_total_duration_seconds.labels(status=status).observe(
                duration_seconds
            )

    def record_comparison_llm_request(self) -> None:
        """Increment LLM request counter for comparison narratives."""
        with self._lock:
            self._comparison_llm_requests_total.inc()

    def record_comparison_llm_failure(self) -> None:
        """Increment LLM failure counter for comparison narratives."""
        with self._lock:
            self._comparison_llm_failures_total.inc()

    def record_comparison_session_compared(self, status: str) -> None:
        """Increment session comparison counter."""
        with self._lock:
            self._comparison_sessions_compared_total.labels(status=status).inc()

    def record_comparison_significant_changes(self, count: int) -> None:
        """Record number of significant changes detected."""
        with self._lock:
            self._comparison_significant_changes_detected_total.inc(count)

    def start_http_server(self, port: int = 8000) -> None:
        """Prometheus scrape endpoint'ini başlat (opsiyonel, sadece local dev)."""
        if not _prometheus_available:
            raise RuntimeError("prometheus_client is not installed")

        with self._lock:
            _start_http_server(port, registry=self._registry)

    @property
    def registry(self) -> CollectorRegistry:
        """Get the underlying Prometheus registry."""
        return self._registry


@contextmanager
def track_ai_request(
    collector: MetricsCollector, backend: str, model: str
) -> Generator[None, None, None]:
    """
    Context manager to track the duration of an AI backend request.

    Kullanım:
        with track_ai_request(metrics, "anthropic", "claude-haiku-4-5-20251001"):
            result = call_anthropic(...)
    """
    start_time = time.monotonic()
    status = "error"
    try:
        yield
        status = "success"
    finally:
        duration = time.monotonic() - start_time
        collector.record_ai_request(
            backend=backend,
            model=model,
            duration_seconds=duration,
            status=status,
        )


_collector: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """Global MetricsCollector singleton döndür."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
