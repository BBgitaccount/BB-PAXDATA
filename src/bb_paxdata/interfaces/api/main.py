from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend
from bb_paxdata.infrastructure.observability.metrics import get_metrics
from bb_paxdata.interfaces.api.dependencies import get_cache, get_db
from bb_paxdata.interfaces.api.routers.v1 import (
    audit_log,
    auth,
    compare,
    corrections,
    dashboard,
    database,
    discourse,
    exports,
    monitoring,
    notifications,
    pipeline,
    prompts,
    provenance,
    queue,
    retention,
    scheduled_reports,
    search,
    settings as settings_router,
    speakers,
    stream,
    templates,
    verdict,
    visualization,
    weight_calibration as weight_calibration_router,
    worldmap,
)
from bb_paxdata.interfaces.api.routers.ws import queue_ws
from bb_paxdata.interfaces.graphql.router import get_graphql_router

settings = get_settings()

# Setup OpenTelemetry Tracing
try:
    from bb_paxdata.infrastructure.observability.tracing import setup_tracing

    setup_tracing(
        service_name=settings.otel_service_name,
        endpoint=settings.otel_exporter_otlp_endpoint,
        enabled=settings.otel_enabled,
    )
except Exception:
    pass

limiter = Limiter(key_func=get_remote_address)

# Setup Sentry Error Tracking
if settings.sentry_dsn:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
        )
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    import structlog

    from bb_paxdata.interfaces.api.routers.ws.queue_ws import listen_to_redis_events

    # Start Redis listener background task with graceful fallback
    redis_listener_task = None
    try:
        redis_listener_task = asyncio.create_task(listen_to_redis_events())
    except Exception as e:
        logger = structlog.get_logger("bb_paxdata.interfaces.api")
        logger.warning(
            "redis_listener_startup_failed",
            error=str(e),
            message="Redis listener başlatılamadı, WebSocket bildirimleri çalışmayacak",
        )

    try:
        yield
    finally:
        if redis_listener_task:
            redis_listener_task.cancel()
            try:
                await redis_listener_task
            except asyncio.CancelledError:
                pass

        from bb_paxdata.infrastructure.container.service_container import (
            ServiceContainer,
        )

        container = ServiceContainer._instance
        if container is not None:
            await container.aclose()


app = FastAPI(
    title="BB-PAXDATA HITL API",
    description="Human-in-the-Loop ve Formül Doğrulama REST Servisi",
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Instrument FastAPI App with OpenTelemetry
if settings.otel_enabled:
    try:
        from bb_paxdata.infrastructure.observability.tracing import (
            instrument_fastapi_app,
        )

        instrument_fastapi_app(app)
    except Exception:
        pass


# Register SlowAPI rate limiter state and handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to capture all unhandled exceptions, log them, report to Sentry, and return 500."""
    import structlog

    struct_logger = structlog.get_logger("bb_paxdata.interfaces.api")
    struct_logger.exception(
        "unhandled_exception", path=request.url.path, method=request.method
    )

    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        pass

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal Server Error",
            "message": str(exc) if settings.debug else "An unexpected error occurred.",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Structured response for HTTP 422 Validation Errors."""
    import structlog

    struct_logger = structlog.get_logger("bb_paxdata.interfaces.api")
    struct_logger.warning(
        "validation_error", path=request.url.path, errors=exc.errors()
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={},
    )


# Correlation ID tracking middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    import uuid

    import structlog

    from bb_paxdata.application.domain.utils.context import set_correlation_id

    # Retrieve correlation ID from headers or generate a new one
    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get(
        "x-correlation-id"
    )
    if not correlation_id:
        correlation_id = f"corr-{uuid.uuid4().hex}"

    # Set correlation ID in contextvars
    set_correlation_id(correlation_id)

    # Bind to structlog contextvars for logging
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    # If OpenTelemetry trace is active, inject correlation_id as span attribute
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            span.set_attribute("correlation_id", correlation_id)
    except ImportError:
        pass

    response = await call_next(request)

    # Return correlation ID in response headers
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# CORS middleware to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)

# Mount versioned API routes
app.include_router(auth.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(queue.router, prefix="/api/v1")
app.include_router(verdict.router, prefix="/api/v1")
app.include_router(discourse.router, prefix="/api/v1")
app.include_router(database.router, prefix="/api/v1")
app.include_router(prompts.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(compare.router, prefix="/api/v1")
app.include_router(speakers.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(provenance.router, prefix="/api/v1")
app.include_router(audit_log.router, prefix="/api/v1")
app.include_router(retention.router, prefix="/api/v1")
app.include_router(corrections.router, prefix="/api/v1")
app.include_router(weight_calibration_router.router, prefix="/api/v1")
app.include_router(monitoring.router, prefix="/api/v1")
app.include_router(stream.router, prefix="/api/v1")
app.include_router(exports.router, prefix="/api/v1/exports")
app.include_router(templates.router, prefix="/api/v1/templates")
app.include_router(scheduled_reports.router, prefix="/api/v1/scheduled-reports")
app.include_router(notifications.router, prefix="/api/v1/notifications")
app.include_router(worldmap.router, prefix="/api/v1")
app.include_router(visualization.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(queue_ws.router, prefix="/api")
app.include_router(get_graphql_router(), prefix="/graphql")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "BB-PAXDATA HITL API",
        "version": settings.version,
        "docs": "/docs",
        "health": "/health",
        "api": "/api/v1",
    }


@app.get("/health")
@limiter.limit("60/minute")
async def health_check(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    cache: RedisCacheBackend = Depends(get_cache),
):
    """Simple health check endpoint returning service status, version and database/cache health."""
    db_healthy = False
    try:
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception:
        db_healthy = False

    if hasattr(cache, "health_check") and callable(cache.health_check):
        cache_healthy = await cache.health_check()
    else:
        cache_healthy = True

    overall_status = "healthy"
    if not db_healthy or not cache_healthy:
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall_status,
        "app_name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "dependencies": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if cache_healthy else "unhealthy",
        },
    }


@app.get("/ready")
@limiter.limit("60/minute")
async def readiness_check(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    cache: RedisCacheBackend = Depends(get_cache),
):
    """Readiness probe - checks if all dependencies are ready to accept traffic."""
    checks = {}

    # Database check
    db_healthy = False
    try:
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        db_healthy = False
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # Redis/Cache check
    cache_healthy = False
    if hasattr(cache, "health_check") and callable(cache.health_check):
        cache_healthy = await cache.health_check()
    else:
        cache_healthy = True

    if not cache_healthy:
        checks["redis"] = {"status": "unhealthy", "error": "Redis connection failed"}

    # Meilisearch check (if configured)
    meilisearch_healthy = False
    if settings.meilisearch_url:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.meilisearch_url}/health")
                meilisearch_healthy = resp.status_code == 200
        except Exception as e:
            checks["meilisearch"] = {"status": "unhealthy", "error": str(e)}

    # Build response
    dependencies = {
        "database": "healthy" if db_healthy else "unhealthy",
        "redis": "healthy" if cache_healthy else "unhealthy",
        "meilisearch": "healthy" if meilisearch_healthy else "unhealthy",
    }

    all_healthy = all(
        dep == "healthy" for dep in dependencies.values() if dep != "unavailable"
    )

    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if all_healthy else "not_ready",
        "app_name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "dependencies": dependencies,
        "checks": checks,
    }


@app.get("/live")
@limiter.limit("60/minute")
async def liveness_check(request: Request, response: Response):
    """Liveness probe - checks if the process is running and responding."""
    return {
        "status": "alive",
        "app_name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "timestamp": __import__("time").time(),
    }


@app.get("/health/circuit-breakers")
@limiter.limit("30/minute")
async def circuit_breaker_status(request: Request):
    """Get circuit breaker status for all AI services."""
    try:
        from bb_paxdata.infrastructure.ai.circuit_breaker import (
            get_all_circuit_breaker_stats,
        )

        stats = get_all_circuit_breaker_stats()
        return {
            "circuit_breakers": stats,
            "total_services": len(stats),
        }
    except Exception as e:
        import structlog

        structlog.get_logger(__name__).error(
            "Failed to get circuit breaker stats", error=str(e)
        )
        return {"circuit_breakers": {}, "total_services": 0, "error": str(e)}


@app.get("/metrics")
def metrics(request: Request):
    """Prometheus scrape endpoint serving internal MetricsCollector registry.

    Requires METRICS_TOKEN header for authentication in production environments.
    """
    # Check for metrics token in production
    if settings.environment == "production" and settings.metrics_token:
        auth_header = request.headers.get("X-Metrics-Token")
        if auth_header != settings.metrics_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing metrics token",
            )

    collector = get_metrics()
    custom_metrics = generate_latest(collector.registry)
    default_metrics = generate_latest(REGISTRY)
    return Response(
        content=custom_metrics + default_metrics,
        media_type=CONTENT_TYPE_LATEST,
    )
