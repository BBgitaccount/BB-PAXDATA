from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bb_paxdata.infrastructure.db.base import Base
from bb_paxdata.infrastructure.messaging.publisher import get_publisher
from bb_paxdata.interfaces.api.dependencies import get_cache, get_db
from bb_paxdata.interfaces.api.main import app

# Use in-memory SQLite for fast database integration testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class MockCacheBackend:
    """Mock cache backend in memory for API testing."""

    def __init__(self):
        self._store = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def clear(self, prefix: str | None = None) -> int:
        self._store.clear()
        return 0

    async def health_check(self) -> bool:
        return True


class MockPublisher:
    """Mock event publisher in memory for API testing."""

    def __init__(self):
        self.published_events = []

    async def publish_event(self, channel: str, event_type: str, data: dict[str, Any]):
        self.published_events.append(
            {"channel": channel, "event_type": event_type, "data": data}
        )


@pytest_asyncio.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Initialize all database tables for the test session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
    )

    async with SessionLocal() as session:
        yield session

    # Cleanup tables and connection
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
def override_dependencies(test_db_session):
    """Automatically overrides FastAPI dependencies for testing."""

    # 1. DB Session Override
    async def _get_db_override():
        yield test_db_session

    # 2. Redis Cache Override
    mock_cache = MockCacheBackend()

    async def _get_cache_override():
        return mock_cache

    # 3. Redis Event Publisher Override
    mock_publisher = MockPublisher()

    async def _get_publisher_override():
        return mock_publisher

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_cache] = _get_cache_override
    app.dependency_overrides[get_publisher] = _get_publisher_override

    yield

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_cache, None)
    app.dependency_overrides.pop(get_publisher, None)
