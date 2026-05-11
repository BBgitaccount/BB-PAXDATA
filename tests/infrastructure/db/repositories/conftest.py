"""In-memory SQLite engine shared across repository tests."""

from collections.abc import AsyncGenerator, Callable

import pytest
from bb_paxdata.infrastructure.db import models as m
from bb_paxdata.infrastructure.db.base import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession], None]:
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


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionTesting = async_sessionmaker(
        bind=engine, autocommit=False, autoflush=False, class_=AsyncSession
    )
    async with SessionTesting() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def seed_panel_speaker_segment(session: AsyncSession) -> None:
    session.add(
        m.Panel(
            panel_id="p1",
            file_name="t.txt",
            file_format="txt",
        )
    )
    session.add(
        m.Speaker(
            speaker_id="sp1",
            full_name="Speaker One",
        )
    )
    await session.flush()
    from bb_paxdata.domain.models.segment import Segment as SegmentDomain

    seg = SegmentDomain(
        id="seg1",
        panel_id="p1",
        primary_speaker_id="sp1",
        word_count=1,
        sentence_count=1,
    )
    session.add(m.Segment.from_domain(seg))
    await session.commit()
