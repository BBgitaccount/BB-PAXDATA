# src/bb_paxdata/interfaces/cli/dependencies.py
"""
CLI komutları için bağımlılık (DI) wiring.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bb_paxdata.application.use_cases.aggregate_bilateral_sentiment import (
    AggregateBilateralSentimentUseCase,
)
from bb_paxdata.application.use_cases.aggregate_panel_topics import (
    AggregatePanelTopicsUseCase,
)
from bb_paxdata.application.use_cases.build_panel_network import (
    BuildPanelNetworkUseCase,
)
from bb_paxdata.infrastructure.repositories.country_repository import (
    BilateralSentimentRepository,
    CountryReferenceRepository,
    DiscourseFlowRepository,
    TopicSynthesisRepository,
)


def _get_database_url() -> str:
    """
    Veritabanı URL'ini proje config/env'den okur.
    """
    import os

    # Default to local sqlite for development
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bb_paxdata.db")


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(_get_database_url(), echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await engine.dispose()


def make_aggregate_bilateral_use_case(
    session: AsyncSession,
) -> AggregateBilateralSentimentUseCase:
    return AggregateBilateralSentimentUseCase(
        ref_repo=CountryReferenceRepository(session),
        sentiment_repo=BilateralSentimentRepository(session),
    )


def make_build_network_use_case(session: AsyncSession) -> BuildPanelNetworkUseCase:
    return BuildPanelNetworkUseCase(
        sentiment_repo=BilateralSentimentRepository(session),
        flow_repo=DiscourseFlowRepository(session),
    )


def make_aggregate_topics_use_case(
    session: AsyncSession,
) -> AggregatePanelTopicsUseCase:
    return AggregatePanelTopicsUseCase(
        ref_repo=CountryReferenceRepository(session),
        synthesis_repo=TopicSynthesisRepository(session),
    )
