import asyncio
import os
import sys
from typing import Any

import streamlit as st
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# project path setup
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

from bb_paxdata.infrastructure.db.repositories.formula_validation import (
    FormulaValidationRepository,
)


def get_database_url() -> str:
    """Build async database URL from .env."""
    url = os.getenv("DATABASE_URL", "sqlite:///./data/paxdata.db")
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    elif url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@st.cache_resource
def get_engine():
    """Create a cached async engine."""
    return create_async_engine(get_database_url(), echo=False)


def run_async(coro):
    """Run an async coroutine in a sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _get_kpi_stats() -> dict[str, Any]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_kpi_stats()


async def _get_formula_health() -> list[dict[str, Any]]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_formula_health()


async def _get_fail_queue(
    formula_name: str | None = None,
    panel_id: str | None = None,
    status_filter: str = "unreviewed",
    limit: int = 50,
) -> list[dict[str, Any]]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_fail_queue_with_context(
            formula_name=formula_name,
            panel_id=panel_id,
            status_filter=status_filter,
            limit=limit,
        )


async def _get_triplet_context(sent_id: str) -> dict[str, str | None]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_triplet_context(sent_id)


async def _get_similar_cases(
    sent_id: str, formula_name: str, country: str | None = None
) -> list[dict[str, Any]]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_similar_cases(
            sent_id=sent_id, formula_name=formula_name, country=country
        )


async def _submit_verdict(
    log_id: int,
    verdict: str,
    corrected_value: float | None,
    note: str | None,
    confidence: str | None,
    justification: str | None,
    reviewer_id: str,
) -> dict[str, Any]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        result = await repo.submit_verdict_atomic(
            log_id=log_id,
            verdict=verdict,
            corrected_value=corrected_value,
            note=note,
            confidence=confidence,
            justification=justification,
            reviewer_id=reviewer_id,
        )
        await session.commit()
        return result


async def _get_audit_trail(limit: int = 10) -> list[dict[str, Any]]:
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        return await repo.get_audit_trail(limit=limit)


async def _start_review(log_id: int, reviewer_id: str):
    engine = get_engine()
    async with AsyncSession(engine) as session:
        repo = FormulaValidationRepository(session)
        result = await repo.start_review(log_id, reviewer_id)
        await session.commit()
        return result
