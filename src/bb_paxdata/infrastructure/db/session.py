"""Database engine, session factory, and lifecycle helpers."""

from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

from sqlalchemy import NullPool, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.db.base import Base

_settings = get_settings()
DATABASE_URL = _settings.database_url or "sqlite+aiosqlite:///paxdata.db"
DATABASE_URL_SYNC = DATABASE_URL.replace("sqlite+aiosqlite", "sqlite").replace(
    "postgresql+asyncpg", "postgresql"
)

_is_postgres = "asyncpg" in DATABASE_URL

# ── Primary async engine (API / FastAPI workers) ──────────────────────────────
_engine_kwargs: dict = {
    "echo": False,
    "future": True,
}

if _is_postgres:
    _engine_kwargs.update(
        {
            "pool_size": _settings.db_pool_size,  # default 5
            "max_overflow": _settings.db_pool_size * 2,  # burst capacity
            "pool_timeout": _settings.db_pool_timeout,  # default 30s
            "pool_recycle": 300,  # recycle connections every 5 min
            "pool_pre_ping": True,  # validate connection before use
        }
    )

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

# ── NullPool engine for CLI workers (forked processes) ───────────────────────
# CLI build commands run in a subprocess. Sharing the QueuePool across forks
# causes "connection already closed" errors on asyncpg.
engine_cli = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False,
    future=True,
)

# ── Optional read-replica engine ─────────────────────────────────────────────
# Set PAXDATA_DATABASE_REPLICA_URL to a PG read replica URL to enable.
# Falls back to the primary engine if not configured.
_REPLICA_URL = _settings.database_replica_url
if _REPLICA_URL and _is_postgres:
    _replica_url = _REPLICA_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine_replica = create_async_engine(
        _replica_url,
        pool_size=_settings.db_pool_size,
        pool_pre_ping=True,
        echo=False,
        future=True,
    )
else:
    engine_replica = engine


class RoutingSession(Session):
    """Custom session that routes read queries to the replica engine."""

    def get_bind(self, mapper=None, clause=None, **kw):
        if self.in_transaction() or self.new or self.dirty or self.deleted:
            return engine.sync_engine

        if clause is not None:
            from sqlalchemy.sql import Select

            if isinstance(clause, Select):
                return engine_replica.sync_engine

        return engine.sync_engine


SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    sync_session_class=RoutingSession,
)

SessionLocalCLI = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine_cli,
    class_=AsyncSession,
    sync_session_class=RoutingSession,
)

if _REPLICA_URL and _is_postgres:
    SessionLocalReplica = async_sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine_replica,
        class_=AsyncSession,
        sync_session_class=RoutingSession,
    )
else:
    SessionLocalReplica = SessionLocal

# ── Sync engine (Alembic migrations, scripts) ────────────────────────────────
engine_sync = create_engine(DATABASE_URL_SYNC, echo=False, future=True)
SessionLocalSync = sessionmaker(autocommit=False, autoflush=False, bind=engine_sync)

# ── Instrument database engines for OpenTelemetry tracing ─────────────────────
if _settings.otel_enabled:
    try:
        from bb_paxdata.infrastructure.observability.tracing import (
            instrument_sqlalchemy_engines,
        )

        instrument_sqlalchemy_engines([engine, engine_cli, engine_replica, engine_sync])
    except Exception:
        pass


# ── Session providers ────────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — uses QueuePool primary engine."""
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


async def get_db_replica() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — uses read replica if configured."""
    async with SessionLocalReplica() as db:
        try:
            yield db
        finally:
            await db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Synchronous database session context manager."""
    db: Session = SessionLocalSync()
    try:
        yield db
    finally:
        db.close()


async def init_db() -> None:
    from bb_paxdata.infrastructure.db import (
        archive_table,  # noqa: F401
        country_models,  # noqa: F401
        dki_table,  # noqa: F401
        drift_events,  # noqa: F401
        human_review_queue,  # noqa: F401
        human_review_table,  # noqa: F401
        models,  # noqa: F401
        sbi_table,  # noqa: F401
        topic_models,  # noqa: F401
    )
    from bb_paxdata.infrastructure.db.country_models import Base as CountryBase
    from bb_paxdata.infrastructure.db.models import OutboxEventORM  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(CountryBase.metadata.create_all)
