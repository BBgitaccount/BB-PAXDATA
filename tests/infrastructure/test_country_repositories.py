# tests/infrastructure/test_country_repositories.py
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from bb_paxdata.domain.enums.country_enums import ReferenceContext
from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.domain.models.country_reference import CountryReference
from bb_paxdata.infrastructure.db.country_models import Base
from bb_paxdata.infrastructure.repositories.country_repository import (
    BilateralSentimentRepository,
    CountryReferenceRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_save_and_retrieve_country_reference(session: AsyncSession) -> None:
    repo = CountryReferenceRepository(session)
    ref = CountryReference(
        panel_id="panel_001",
        speaker_country="TR",
        referenced_country="US",
        sentence_index=3,
        reference_context=ReferenceContext.NEGOTIATION,
        raw_sentiment_score=0.4,
    )
    await repo.save(ref)
    await session.commit()

    results = await repo.get_by_panel("panel_001")
    assert len(results) == 1
    assert results[0].speaker_country == "TR"
    assert results[0].reference_context == ReferenceContext.NEGOTIATION


@pytest.mark.asyncio
async def test_bilateral_sentiment_upsert(session: AsyncSession) -> None:
    repo = BilateralSentimentRepository(session)
    s1 = BilateralSentiment(
        panel_id="p1",
        from_country="TR",
        to_country="US",
        total_mentions=1,
        avg_sentiment=0.5,
    )
    saved = await repo.upsert(s1)
    await session.commit()

    s2 = saved.with_new_reference(sentiment=-0.2, power_level=0.8)
    await repo.upsert(s2)
    await session.commit()

    fetched = await repo.get_by_pair("TR", "US", "p1")
    assert fetched is not None
    assert fetched.total_mentions == 2
