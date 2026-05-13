"""
MetricsCollector module for Prometheus integration.
Provides thread-safe prometheus metric collection and a singleton interface.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

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
            self, name: str, documentation: str, *args: Any, **kwargs: Any
        ) -> None:
            pass

        def labels(self, **kwargs: Any) -> Any:
            return self

        def inc(self, amount: float = 1) -> None:
            pass

    class Gauge:  # type: ignore
        def __init__(
            self, name: str, documentation: str, *args: Any, **kwargs: Any
        ) -> None:
            pass

        def labels(self, **kwargs: Any) -> Any:
            return self

        def set(self, value: float) -> None:
            pass

        def inc(self, amount: float = 1) -> None:
            pass

        def dec(self, amount: float = 1) -> None:
            pass

    class Histogram:  # type: ignore
        def __init__(
            self, name: str, documentation: str, *args: Any, **kwargs: Any
        ) -> None:
            pass

        def labels(self, **kwargs: Any) -> Any:
            return self

        def observe(self, amount: float) -> None:
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
) -> Iterator[None]:
    """
    Context manager to track the duration of an AI backend request.

    Kullanım:
        with track_ai_request(metrics, "anthropic", "claude-haiku-4-5-20251001"):
            result = call_anthropic(...)
    """
    import time

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
