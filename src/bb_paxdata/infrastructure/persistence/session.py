from __future__ import annotations

from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def get_session_factory(database_url: str | None) -> Any:
    """Async session factory oluşturur."""
    if database_url is None:
        raise ValueError("Database URL cannot be None")

    engine = create_async_engine(database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session(session_factory: Any) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI veya diğer dependency injection'lar için session generator."""
    async with session_factory() as session:
        yield session
