import pytest
from bb_paxdata.config.logging import add_otel_trace_info
from bb_paxdata.infrastructure.ai.base import CompletionOptions, CompletionResult
from bb_paxdata.infrastructure.observability.tracing import (
    get_tracer,
    instrument_fastapi_app,
    instrument_sqlalchemy_engines,
    is_otel_available,
    setup_tracing,
    trace_ai_completion,
)


def test_otel_availability():
    # Should run cleanly and return a boolean
    available = is_otel_available()
    assert isinstance(available, bool)


def test_setup_tracing_no_crash():
    # Should run cleanly and not raise exceptions even when disabled or endpoints are unreachable
    setup_tracing(
        service_name="test-service", endpoint="http://localhost:4317", enabled=False
    )
    setup_tracing(
        service_name="test-service", endpoint="http://localhost:4317", enabled=True
    )


def test_get_tracer():
    tracer = get_tracer("test-tracer")
    if is_otel_available():
        assert tracer is not None
    else:
        assert tracer is None


@pytest.mark.asyncio
async def test_trace_ai_completion_wrapper():
    # A dummy async complete function
    async def dummy_complete(user_message, options=None):
        return CompletionResult(
            content="test response",
            parsed=None,
            backend="dummy",
            model="test-model",
            tokens_used=10,
            latency_ms=100,
            success=True,
        )

    wrapped = trace_ai_completion(dummy_complete, "dummy", "test-model")
    result = await wrapped("hello", CompletionOptions())
    assert result.success is True
    assert result.content == "test response"


def test_add_otel_trace_info():
    event_dict = {"event": "test log"}
    processed_dict = add_otel_trace_info(None, "info", event_dict)
    assert "event" in processed_dict
    # If no trace is active, trace_id/span_id should not be injected
    assert "trace_id" not in processed_dict


def test_instrumentation_helpers_no_crash():
    # Verify instrumentation helper functions handle None and run without throwing
    instrument_sqlalchemy_engines([None])
    instrument_fastapi_app(None)


def test_correlation_id_context_lifecycle():
    from bb_paxdata.application.domain.utils.context import (
        get_correlation_id,
        set_correlation_id,
    )

    # Initially None
    set_correlation_id(None)
    assert get_correlation_id() is None

    # Set correlation ID
    set_correlation_id("test-corr-id-123")
    assert get_correlation_id() == "test-corr-id-123"

    # Reset
    set_correlation_id(None)
    assert get_correlation_id() is None


def test_domain_model_auto_populates_correlation_id_from_context():
    from bb_paxdata.application.domain.models.analysis import Analysis
    from bb_paxdata.application.domain.utils.context import set_correlation_id

    # Set context correlation ID
    set_correlation_id("auto-corr-999")

    # Instantiate analysis and record event without explicit correlation ID
    analysis = Analysis()
    analysis.record_event(
        event_type="AnalysisCompleted",
        payload={"result": "ok"},
        aggregate_id="sent-123",
    )

    # Verify event carries the context's correlation ID
    events = analysis.get_events()
    assert len(events) == 1
    assert events[0]["correlation_id"] == "auto-corr-999"

    # Reset context
    set_correlation_id(None)


@pytest.mark.asyncio
async def test_fastapi_correlation_id_middleware_generates_new_id():
    from bb_paxdata.application.domain.utils.context import get_correlation_id
    from fastapi import FastAPI, Request
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()

    # Track what the correlation ID was during the request execution
    captured_corr_id = None

    @app.middleware("http")
    async def middleware_under_test(request: Request, call_next):
        # We simulate main.py middleware manually inside the test context
        import uuid

        import structlog
        from bb_paxdata.application.domain.utils.context import set_correlation_id

        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get(
            "x-correlation-id"
        )
        if not correlation_id:
            correlation_id = f"corr-{uuid.uuid4().hex}"

        set_correlation_id(correlation_id)
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @app.get("/test-endpoint")
    async def handler():
        nonlocal captured_corr_id
        captured_corr_id = get_correlation_id()
        return {"status": "ok"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/test-endpoint")

    # Check that middleware generated a correlation ID and returned it
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    assert response.headers["X-Correlation-ID"].startswith("corr-")

    # Check that the ID was active during handler execution
    assert captured_corr_id == response.headers["X-Correlation-ID"]


@pytest.mark.asyncio
async def test_fastapi_correlation_id_middleware_preserves_existing_id():
    from bb_paxdata.application.domain.utils.context import get_correlation_id
    from fastapi import FastAPI, Request
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()
    captured_corr_id = None

    @app.middleware("http")
    async def middleware_under_test(request: Request, call_next):
        import uuid

        import structlog
        from bb_paxdata.application.domain.utils.context import set_correlation_id

        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get(
            "x-correlation-id"
        )
        if not correlation_id:
            correlation_id = f"corr-{uuid.uuid4().hex}"

        set_correlation_id(correlation_id)
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @app.get("/test-endpoint")
    async def handler():
        nonlocal captured_corr_id
        captured_corr_id = get_correlation_id()
        return {"status": "ok"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            "/test-endpoint", headers={"X-Correlation-ID": "incoming-id-xyz"}
        )

    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == "incoming-id-xyz"
    assert captured_corr_id == "incoming-id-xyz"
