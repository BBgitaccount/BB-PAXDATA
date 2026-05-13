"""Database engine, session factory, and lifecycle helpers."""

from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from bb_paxdata.infrastructure.db.base import Base

DATABASE_URL = "sqlite+aiosqlite:///bb-paxdata.db"
DATABASE_URL_SYNC = "sqlite:///bb-paxdata.db"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

engine_sync = create_engine(DATABASE_URL_SYNC, echo=False, future=True)
SessionLocalSync = sessionmaker(autocommit=False, autoflush=False, bind=engine_sync)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:
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
    from bb_paxdata.infrastructure.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
