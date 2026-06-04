from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.observability.metrics import get_metrics
from bb_paxdata.interfaces.api.routers.v1 import (
    dashboard,
    database,
    discourse,
    prompts,
    queue,
    search,
    verdict,
)
from bb_paxdata.interfaces.api.routers.ws import queue_ws
from bb_paxdata.interfaces.graphql.router import graphql_router

settings = get_settings()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="BB-PAXDATA HITL API",
    description="Human-in-the-Loop ve Formül Doğrulama REST Servisi",
    version=settings.version,
    debug=settings.debug,
)

# Register SlowAPI rate limiter state and handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

# CORS middleware to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production environment will narrow this down
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount versioned API routes
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(queue.router, prefix="/api/v1")
app.include_router(verdict.router, prefix="/api/v1")
app.include_router(discourse.router, prefix="/api/v1")
app.include_router(database.router, prefix="/api/v1")
app.include_router(prompts.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(queue_ws.router, prefix="/api")
app.include_router(graphql_router, prefix="/graphql")


@app.get("/health")
@limiter.limit("60/minute")
def health_check(request: Request):
    """Simple health check endpoint returning service status and version."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
    }


@app.get("/metrics")
def metrics():
    """Prometheus scrape endpoint serving internal MetricsCollector registry."""
    collector = get_metrics()
    return Response(
        content=generate_latest(collector.registry),  # type: ignore
        media_type=CONTENT_TYPE_LATEST,
    )
