"""
Structlog configuration for BB-PAXDATA.

JSON ve pretty konsol çıktısı desteği ile yapılandırılmış logging.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import structlog
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer
from structlog.types import Processor

# Global flag to prevent multiple configurations
_configured = False


def add_otel_trace_info(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Injects current trace_id and span_id into the log event dict if OpenTelemetry is active."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            ctx = span.get_span_context()
            event_dict["trace_id"] = f"{ctx.trace_id:032x}"
            event_dict["span_id"] = f"{ctx.span_id:016x}"
    except Exception:
        pass
    return event_dict


def add_performance_markers(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add performance markers for timing analysis."""
    if "duration_ms" not in event_dict and "performance" in event_dict:
        # Auto-calculate duration if start_time was set
        perf_data = event_dict["performance"]
        if isinstance(perf_data, dict) and "start_time" in perf_data:
            duration_ms = (time.time() - perf_data["start_time"]) * 1000
            event_dict["duration_ms"] = round(duration_ms, 2)
            event_dict["performance_stage"] = perf_data.get("stage", "unknown")
    return event_dict


def setup_logging(
    level: str = "INFO",  # "DEBUG" | "INFO" | "WARNING" | "ERROR"
    pretty: bool = True,  # True = renkli konsol, False = JSON satırı
    log_file: Path | None = None,  # Dosyaya da yazmak için
    session_id: str | None = None,  # Her log satırına eklenecek sabit alan
) -> None:
    """
    Tüm uygulama için structlog yapılandırır.
    main() veya CLI entry point'inin en başında bir kez çağrılır.
    """
    global _configured

    if _configured:
        return

    # Ortak processor'lar
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # contextvars entegrasyonu
        add_otel_trace_info,  # OpenTelemetry tracing context
        add_performance_markers,  # Performance timing markers
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Structlog yapılandırması
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Console Handler (pretty / colored or raw JSON)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=ConsoleRenderer(colors=True) if pretty else JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )

    handlers: list[logging.Handler] = [console_handler]

    # File Handler (JSON format)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=JSONRenderer(),
                foreign_pre_chain=shared_processors,
            )
        )
        handlers.append(file_handler)

    # Configure root logger with handlers
    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    for h in handlers:
        root_logger.addHandler(h)

    # Set logging level
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Session_id context'e ekle
    if session_id:
        structlog.contextvars.bind_contextvars(session_id=session_id)

    _configured = True


def get_logger(name: str, **initial_context: Any) -> Any:
    """
    Modüllerin `structlog.get_logger(__name__)` yerine kullanabileceği
    kısa yol. initial_context varsa bind eder.

    Kullanım:
        logger = get_logger(__name__, component="batch")
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


def is_configured() -> bool:
    """Logging yapılandırıldı mı kontrol et."""
    return _configured


def reset_configuration() -> None:
    """Test için yapılandırmayı sıfırla."""
    global _configured
    _configured = False


@contextmanager
def performance_logger(logger: Any, stage: str) -> Generator[None, None, None]:
    """Context manager for tracking performance of code blocks.

    Usage:
        with performance_logger(logger, "ai_completion"):
            result = await ai_service.complete(...)
    """
    start_time = time.time()
    logger.info(
        "performance.start", performance={"stage": stage, "start_time": start_time}
    )
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "performance.end",
            performance={"stage": stage, "start_time": start_time},
            duration_ms=round(duration_ms, 2),
        )
