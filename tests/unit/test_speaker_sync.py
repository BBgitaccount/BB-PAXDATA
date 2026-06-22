import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bb_paxdata.application.use_cases.speaker_registry_use_case import (
    SpeakerRegistryUseCase,
)
from bb_paxdata.infrastructure.db import models as m
from bb_paxdata.infrastructure.db.base import Base
from bb_paxdata.infrastructure.db.repositories.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
async def test_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine, autocommit=False, autoflush=False, class_=AsyncSession
    )
    yield factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_speaker_registry_syncs_to_entries(test_session_factory):
    uow = SqlAlchemyUnitOfWork(test_session_factory)
    use_case = SpeakerRegistryUseCase(uow)

    # 1. Add a speaker with raw name that needs normalization
    async with uow:
        # I + combining dot above (U+0307) -> NFC normalized to İSMAIL
        raw_name = "I\u0307SMAIL"
        speaker = await use_case.detect_or_create_speaker(
            raw_name=raw_name, context={"is_active": True}
        )

        # Check that speaker is created with normalized names
        assert speaker.canonical_name == "İSMAIL"
        assert speaker.display_name == "İSMAIL"

    # Check entries table is populated
    async with test_session_factory() as session:
        res = await session.execute(select(m.Entry))
        entries = res.scalars().all()
        entry_names = [e.person for e in entries]
        assert "İSMAIL" in entry_names
