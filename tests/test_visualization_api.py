# tests/test_visualization_api.py

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bb_paxdata.infrastructure.auth.jwt_auth import create_jwt
from bb_paxdata.infrastructure.db.base import Base as MainBase
from bb_paxdata.infrastructure.db.country_models import (
    Base as CountryBase,
    BilateralSentimentTable,
    CountryReferenceTable,
)
from bb_paxdata.infrastructure.db.models import (
    CountryPairSentiment,
    CountryStat,
    File,
)
from bb_paxdata.interfaces.api.dependencies import get_cache, get_db
from bb_paxdata.interfaces.api.main import app

client = TestClient(app)

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


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Initialize all database tables for both declarative bases in the test session
    async with engine.begin() as conn:
        await conn.run_sync(MainBase.metadata.create_all)
        await conn.run_sync(CountryBase.metadata.create_all)

    SessionLocal = async_sessionmaker(
        autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
    )

    async with SessionLocal() as session:
        yield session

    # Cleanup tables and connection
    async with engine.begin() as conn:
        await conn.run_sync(MainBase.metadata.drop_all)
        await conn.run_sync(CountryBase.metadata.drop_all)
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

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_cache] = _get_cache_override

    yield

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_cache, None)


@pytest.fixture
def auth_headers():
    """Returns authorization headers for an admin reviewer."""
    token = create_jwt("admin@paxdata.local", roles=["admin"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_viz_data(test_db_session: AsyncSession):
    # 1. Seed File (Session)
    session1 = File(
        file_id="session-1",
        file_name="session_1.txt",
        title="Session 1 Title",
        idempotency_key="key-1",
    )
    session2 = File(
        file_id="session-2",
        file_name="session_2.txt",
        title="Session 2 Title",
        idempotency_key="key-2",
    )
    test_db_session.add_all([session1, session2])
    await test_db_session.flush()

    # 2. Seed CountryStats
    stat1 = CountryStat(
        country="Turkiye",
        file_id="session-1",
        n_segments=10,
        n_sentences=50,
        total_words=1000,
        avg_sentiment=0.4,
        dominant_emotion="joy",
        dominant_topic="economy",
    )
    stat2 = CountryStat(
        country="Greece",
        file_id="session-1",
        n_segments=5,
        n_sentences=25,
        total_words=500,
        avg_sentiment=-0.2,
        dominant_emotion="anger",
        dominant_topic="border",
    )
    stat3 = CountryStat(
        country="Turkiye",
        file_id="session-2",
        n_segments=12,
        n_sentences=60,
        total_words=1200,
        avg_sentiment=0.2,
        dominant_emotion="neutral",
        dominant_topic="trade",
    )
    test_db_session.add_all([stat1, stat2, stat3])

    # 3. Seed CountryReferences
    ref1 = CountryReferenceTable(
        id="ref-1",
        file_id="session-1",
        speaker_country="Turkiye",
        speaker_id="speaker-1",
        referenced_country="Greece",
        sentence_index=5,
        reference_context="PRAISE",
        raw_sentiment_score=0.8,
        speaker_power_level=0.9,
    )
    ref2 = CountryReferenceTable(
        id="ref-2",
        file_id="session-1",
        speaker_country="Greece",
        speaker_id="speaker-2",
        referenced_country="Turkiye",
        sentence_index=12,
        reference_context="ACCUSATION",
        raw_sentiment_score=-0.7,
        speaker_power_level=0.6,
    )
    ref3 = CountryReferenceTable(
        id="ref-3",
        file_id="session-2",
        speaker_country="Turkiye",
        speaker_id="speaker-1",
        referenced_country="Greece",
        sentence_index=8,
        reference_context="NEUTRAL_MENTION",
        raw_sentiment_score=0.1,
        speaker_power_level=0.9,
    )
    test_db_session.add_all([ref1, ref2, ref3])

    # 4. Seed BilateralSentiments
    bs1 = BilateralSentimentTable(
        id="bs-1",
        file_id="session-1",
        from_country="Turkiye",
        to_country="Greece",
        total_mentions=5,
        avg_sentiment=0.8,
        interaction_count=3,
        relationship_type="PARTNER",
        affinity_score=0.6,
        power_weighted_score=0.7,
        diplomatic_distance=0.3,
    )
    bs2 = BilateralSentimentTable(
        id="bs-2",
        file_id="session-1",
        from_country="Greece",
        to_country="Turkiye",
        total_mentions=4,
        avg_sentiment=-0.7,
        interaction_count=2,
        relationship_type="CAUTIOUS",
        affinity_score=0.2,
        power_weighted_score=0.3,
        diplomatic_distance=0.8,
    )
    bs3 = BilateralSentimentTable(
        id="bs-3",
        file_id="session-2",
        from_country="Turkiye",
        to_country="Greece",
        total_mentions=2,
        avg_sentiment=0.1,
        interaction_count=1,
        relationship_type="NEUTRAL",
        affinity_score=0.4,
        power_weighted_score=0.5,
        diplomatic_distance=0.5,
    )
    test_db_session.add_all([bs1, bs2, bs3])

    # 5. Seed CountryPairSentiment (Global)
    cps1 = CountryPairSentiment(
        from_country="Turkiye",
        to_country="Greece",
        total_mentions=7,
        avg_sentiment=0.45,
        interaction_count=4,
        relationship_type="PARTNER",
        affinity_score=0.5,
        power_weighted_score=0.6,
        diplomatic_distance=0.4,
    )
    cps2 = CountryPairSentiment(
        from_country="Greece",
        to_country="Turkiye",
        total_mentions=4,
        avg_sentiment=-0.7,
        interaction_count=2,
        relationship_type="CAUTIOUS",
        affinity_score=0.2,
        power_weighted_score=0.3,
        diplomatic_distance=0.8,
    )
    test_db_session.add_all([cps1, cps2])

    await test_db_session.commit()


@pytest.mark.asyncio
async def test_get_country_nodes(seed_viz_data, auth_headers):
    # Verify GET /api/v1/viz/country-nodes
    response = client.get("/api/v1/viz/country-nodes", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

    turkiye_node = next(n for n in data if n["country"] == "Turkiye")
    assert turkiye_node["iso_alpha3"] == "TUR"
    assert turkiye_node["praise_count"] == 1
    assert turkiye_node["accusation_count"] == 0
    assert turkiye_node["neutral_count"] == 1
    assert "session-1" in turkiye_node["sessions"]
    assert "session-2" in turkiye_node["sessions"]


@pytest.mark.asyncio
async def test_get_bilateral_flows(seed_viz_data, auth_headers):
    # Verify GET /api/v1/viz/bilateral-flows?min_interactions=2
    response = client.get(
        "/api/v1/viz/bilateral-flows?min_interactions=2", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Greece to Turkiye
    greece_flow = next(f for f in data if f["from_country"] == "Greece")
    assert greece_flow["to_country"] == "Turkiye"
    assert greece_flow["interaction_count"] == 2
    assert greece_flow["relationship_type"] == "CAUTIOUS"


@pytest.mark.asyncio
async def test_redis_cache_hits(seed_viz_data, auth_headers, capsys):
    # First request
    res1 = client.get("/api/v1/viz/sentiment-matrix", headers=auth_headers)
    assert res1.status_code == 200

    # Second request
    res2 = client.get("/api/v1/viz/sentiment-matrix", headers=auth_headers)
    assert res2.status_code == 200
    assert res1.json() == res2.json()

    # Verify stdout contained "cache hit"
    captured = capsys.readouterr()
    assert "cache hit" in captured.out or "cache hit" in captured.err
