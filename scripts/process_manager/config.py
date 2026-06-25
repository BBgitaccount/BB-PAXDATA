"""
Service configuration for process manager.
Defines all services, their dependencies, and health check endpoints.
"""

from dataclasses import dataclass, field
from enum import Enum


class ServiceType(Enum):
    PROCESS = "process"  # Direct process execution
    PYTHON = "python"  # Python script via poetry
    NODE = "node"  # Node.js script via npm
    SYSTEM = "system"  # System service (requires manual installation)


@dataclass
class ServiceConfig:
    """Configuration for a single service."""

    name: str
    service_type: ServiceType
    command: str
    working_dir: str
    port: int | None = None
    health_check_url: str | None = None
    health_check_interval: int = 10
    startup_timeout: int = 60
    dependencies: list[str] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    log_file: str | None = None
    auto_restart: bool = True
    restart_delay: int = 5
    max_restarts: int = 3


# Service definitions based on docker-compose.yml
SERVICES: dict[str, ServiceConfig] = {
    "postgres": ServiceConfig(
        name="postgres",
        service_type=ServiceType.SYSTEM,
        command="pg_ctl start -D <data_dir>",
        working_dir=".",
        port=5432,
        health_check_url=None,
        health_check_interval=5,
        startup_timeout=30,
        dependencies=[],
        log_file="logs/postgres.log",
        auto_restart=True,
    ),
    "redis": ServiceConfig(
        name="redis",
        service_type=ServiceType.PROCESS,
        command="redis-server",
        working_dir=".",
        port=6379,
        health_check_url=None,
        health_check_interval=5,
        startup_timeout=10,
        dependencies=[],
        log_file="logs/redis.log",
        auto_restart=True,
    ),
    "meilisearch": ServiceConfig(
        name="meilisearch",
        service_type=ServiceType.PROCESS,
        command="meilisearch --master-key=paxdata-meilisearch-key --http-addr=127.0.0.1:7700",
        working_dir=".",
        port=7700,
        health_check_url="http://localhost:7700/health",
        health_check_interval=5,
        startup_timeout=15,
        dependencies=[],
        log_file="logs/meilisearch.log",
        auto_restart=True,
    ),
    "minio": ServiceConfig(
        name="minio",
        service_type=ServiceType.PROCESS,
        command="minio server ./data/minio --console-address :9001",
        working_dir=".",
        port=9000,
        health_check_url="http://localhost:9000/minio/health/live",
        health_check_interval=10,
        startup_timeout=20,
        dependencies=[],
        log_file="logs/minio.log",
        auto_restart=True,
    ),
    "api": ServiceConfig(
        name="api",
        service_type=ServiceType.PYTHON,
        command="uvicorn bb_paxdata.interfaces.api.main:app --host 0.0.0.0 --port 8000 --reload",
        working_dir=".",
        port=8000,
        health_check_url="http://localhost:8000/health",
        health_check_interval=10,
        startup_timeout=180,
        dependencies=["postgres", "redis", "meilisearch"],
        env_vars={
            "PAXDATA_DATABASE_MODE": "postgresql",
            "PAXDATA_DATABASE_URL": "postgresql+asyncpg://paxdata_user:paxdata_password@localhost:5432/paxdata_db",
            "PAXDATA_REDIS_URL": "redis://localhost:6379/0",
            "PAXDATA_MEILISEARCH_URL": "http://localhost:7700",
            "PAXDATA_ENVIRONMENT": "development",
            "PAXDATA_DEBUG": "true",
        },
        log_file="logs/api.log",
        auto_restart=True,
    ),
    "web": ServiceConfig(
        name="web",
        service_type=ServiceType.NODE,
        command="npm run dev -- --host",
        working_dir="src/bb_paxdata/interfaces/web",
        port=5173,
        health_check_url="http://localhost:5173",
        health_check_interval=10,
        startup_timeout=30,
        dependencies=["api"],
        env_vars={
            "VITE_API_URL": "http://localhost:8000",
        },
        log_file="logs/web.log",
        auto_restart=True,
    ),
    "celery-worker-cpu": ServiceConfig(
        name="celery-worker-cpu",
        service_type=ServiceType.PYTHON,
        command="celery -A bb_paxdata.infrastructure.tasks.celery_app worker -Q ai_cpu --loglevel=info --concurrency=2",
        working_dir=".",
        port=None,
        health_check_url=None,
        health_check_interval=15,
        startup_timeout=30,
        dependencies=["postgres", "redis", "api"],
        env_vars={
            "PAXDATA_DATABASE_MODE": "postgresql",
            "PAXDATA_DATABASE_URL": "postgresql+asyncpg://paxdata_user:paxdata_password@localhost:5432/paxdata_db",
            "PAXDATA_REDIS_URL": "redis://localhost:6379/0",
        },
        log_file="logs/celery-cpu.log",
        auto_restart=True,
    ),
    "celery-worker-io": ServiceConfig(
        name="celery-worker-io",
        service_type=ServiceType.PYTHON,
        command="celery -A bb_paxdata.infrastructure.tasks.celery_app worker -Q graph_io --loglevel=info --concurrency=4",
        working_dir=".",
        port=None,
        health_check_url=None,
        health_check_interval=15,
        startup_timeout=30,
        dependencies=["postgres", "redis", "meilisearch", "api"],
        env_vars={
            "PAXDATA_DATABASE_MODE": "postgresql",
            "PAXDATA_DATABASE_URL": "postgresql+asyncpg://paxdata_user:paxdata_password@localhost:5432/paxdata_db",
            "PAXDATA_REDIS_URL": "redis://localhost:6379/0",
            "PAXDATA_MEILISEARCH_URL": "http://localhost:7700",
        },
        log_file="logs/celery-io.log",
        auto_restart=True,
    ),
    "celery-beat": ServiceConfig(
        name="celery-beat",
        service_type=ServiceType.PYTHON,
        command="celery -A bb_paxdata.infrastructure.tasks.celery_app beat --loglevel=info",
        working_dir=".",
        port=None,
        health_check_url=None,
        health_check_interval=15,
        startup_timeout=30,
        dependencies=["postgres", "redis", "api"],
        env_vars={
            "PAXDATA_DATABASE_MODE": "postgresql",
            "PAXDATA_DATABASE_URL": "postgresql+asyncpg://paxdata_user:paxdata_password@localhost:5432/paxdata_db",
            "PAXDATA_REDIS_URL": "redis://localhost:6379/0",
        },
        log_file="logs/celery-beat.log",
        auto_restart=True,
    ),
    "flower": ServiceConfig(
        name="flower",
        service_type=ServiceType.PYTHON,
        command="celery --broker=redis://localhost:6379/0 flower --port=5555",
        working_dir=".",
        port=5555,
        health_check_url="http://localhost:5555",
        health_check_interval=10,
        startup_timeout=15,
        dependencies=["redis"],
        log_file="logs/flower.log",
        auto_restart=True,
    ),
    "prometheus": ServiceConfig(
        name="prometheus",
        service_type=ServiceType.PROCESS,
        command="prometheus --config.file=src/bb_paxdata/infrastructure/observability/prometheus.yml --storage.tsdb.retention.time=15d",
        working_dir=".",
        port=9090,
        health_check_url="http://localhost:9090/-/healthy",
        health_check_interval=10,
        startup_timeout=20,
        dependencies=[],
        log_file="logs/prometheus.log",
        auto_restart=True,
    ),
    "grafana": ServiceConfig(
        name="grafana",
        service_type=ServiceType.PROCESS,
        command="grafana-server --config=src/bb_paxdata/infrastructure/observability/grafana/grafana.ini",
        working_dir=".",
        port=3000,
        health_check_url="http://localhost:3000/api/health",
        health_check_interval=10,
        startup_timeout=30,
        dependencies=["prometheus"],
        log_file="logs/grafana.log",
        auto_restart=True,
    ),
    "jaeger": ServiceConfig(
        name="jaeger",
        service_type=ServiceType.PROCESS,
        command="jaeger-all-in-one --collector.otlp.grpc.host-port=:4317",
        working_dir=".",
        port=16686,
        health_check_url=None,
        health_check_interval=10,
        startup_timeout=20,
        dependencies=[],
        log_file="logs/jaeger.log",
        auto_restart=True,
    ),
}


def get_startup_order() -> list[str]:
    """Calculate service startup order based on dependencies."""
    started = set()
    order = []

    def can_start(service_name: str) -> bool:
        config = SERVICES[service_name]
        return all(dep in started for dep in config.dependencies)

    while len(order) < len(SERVICES):
        progress = False
        for name in SERVICES:
            if name not in order and can_start(name):
                order.append(name)
                started.add(name)
                progress = True

        if not progress:
            # Circular dependency or missing dependency
            remaining = [name for name in SERVICES if name not in order]
            raise ValueError(f"Cannot resolve dependencies for: {remaining}")

    return order


def get_service_config(name: str) -> ServiceConfig:
    """Get service configuration by name."""
    if name not in SERVICES:
        raise ValueError(f"Unknown service: {name}")
    return SERVICES[name]
