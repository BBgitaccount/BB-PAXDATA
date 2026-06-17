"""
OpenTelemetry Tracing configuration and helpers for BB-PAXDATA.
Allows distributed tracing of FastAPI requests, database queries, and AI latency.
"""

from __future__ import annotations

import functools
from typing import Any

# Graceful import check in case dependencies are not fully loaded/present
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    _otel_available = True
except ImportError:
    _otel_available = False

_tracing_configured = False


def is_otel_available() -> bool:
    """Check if OpenTelemetry dependencies are installed."""
    return _otel_available


def get_tracer(name: str = "bb-paxdata") -> Any:
    """Get a tracer instance if OpenTelemetry is available, otherwise return None."""
    if _otel_available:
        return trace.get_tracer(name)
    return None


def setup_tracing(
    service_name: str = "bb-paxdata",
    endpoint: str = "http://localhost:4317",
    enabled: bool = False,
) -> None:
    """
    Configures the global OpenTelemetry TracerProvider and Exporters.
    Safe to call multiple times (will only initialize once).
    """
    global _tracing_configured
    if _tracing_configured or not enabled or not _otel_available:
        return

    try:
        resource = Resource.create(attributes={"service.name": service_name})
        provider = TracerProvider(resource=resource)

        # Configure OTLP Exporter if endpoint is specified
        if endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            except Exception as ex:
                import structlog

                structlog.get_logger(__name__).warning(
                    "Failed to initialize OTLP gRPC exporter, falling back to ConsoleSpanExporter",
                    error=str(ex),
                )
                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        else:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)
        _tracing_configured = True

        import structlog

        structlog.get_logger(__name__).info(
            "OpenTelemetry tracing configured successfully",
            service_name=service_name,
            endpoint=endpoint,
        )
    except Exception as e:
        import structlog

        structlog.get_logger(__name__).warning(
            "Failed to configure OpenTelemetry tracing", error=str(e)
        )


def instrument_sqlalchemy_engines(engines: list[Any]) -> None:
    """Instruments a list of SQLAlchemy engines for tracing."""
    if not _otel_available:
        return

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        instrumentor = SQLAlchemyInstrumentor()
        for engine in engines:
            if engine is not None:
                try:
                    if hasattr(engine, "sync_engine"):
                        instrumentor.instrument(engine=engine.sync_engine)
                    else:
                        instrumentor.instrument(engine=engine)
                except Exception as ex:
                    import structlog

                    structlog.get_logger(__name__).warning(
                        "Failed to instrument individual SQLAlchemy engine",
                        error=str(ex),
                    )
    except Exception as e:
        import structlog

        structlog.get_logger(__name__).warning(
            "Failed to initialize SQLAlchemy instrumentation", error=str(e)
        )


def instrument_fastapi_app(app: Any) -> None:
    """Instruments a FastAPI application."""
    if not _otel_available:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as e:
        import structlog

        structlog.get_logger(__name__).warning(
            "Failed to instrument FastAPI application", error=str(e)
        )


def trace_ai_completion(func: Any, backend_name: str, model_name: str) -> Any:
    """Decorator/wrapper for tracing AI Client complete operations."""
    if not _otel_available:
        return func

    @functools.wraps(func)
    async def wrapper(
        user_message: str, options: Any = None, *args: Any, **kwargs: Any
    ) -> Any:
        tracer = trace.get_tracer("bb-paxdata")
        with tracer.start_as_current_span(
            f"ai.complete.{backend_name}",
            kind=trace.SpanKind.CLIENT,
        ) as span:
            span.set_attribute("ai.backend", backend_name)
            span.set_attribute("ai.model", model_name)
            if options:
                span.set_attribute(
                    "ai.temperature", getattr(options, "temperature", 0.1)
                )
                span.set_attribute(
                    "ai.max_tokens", getattr(options, "max_tokens", 1024)
                )
                span.set_attribute("ai.json_mode", getattr(options, "json_mode", True))

            try:
                result = await func(user_message, options, *args, **kwargs)
                if result:
                    span.set_attribute("ai.success", getattr(result, "success", False))
                    span.set_attribute(
                        "ai.tokens_used", getattr(result, "tokens_used", 0)
                    )
                    span.set_attribute(
                        "ai.latency_ms", getattr(result, "latency_ms", 0)
                    )
                    if getattr(result, "error", None):
                        span.set_attribute("ai.error", str(result.error))
                return result
            except Exception as e:
                span.set_attribute("ai.success", False)
                span.set_attribute("ai.error", str(e))
                span.record_exception(e)
                span.set_status(
                    trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                )
                raise

    return wrapper
