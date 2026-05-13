"""Unit of Work transaction behaviour."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.db.repositories.sentence import SentenceRepository
from bb_paxdata.infrastructure.db.repositories.unit_of_work import SqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession

from tests.infrastructure.db.repositories.conftest import seed_panel_speaker_segment


async def test_uow_commits_on_success(
    session_factory: Callable[[], AsyncSession]
) -> None:
    async with session_factory() as session:
        await seed_panel_speaker_segment(session)

    uow = SqlAlchemyUnitOfWork(session_factory)
    async with uow:
        await uow.sentences.add(
            Sentence(id="u1", text="committed", speaker_id="sp1", segment_id="seg1")
        )

    async with session_factory() as session:
        check = await SentenceRepository(session).get("u1")
        assert check is not None
        assert check.text == "committed"


async def test_uow_rollbacks_on_exception(
    session_factory: Callable[[], AsyncSession]
) -> None:
    async with session_factory() as session:
        await seed_panel_speaker_segment(session)

    with pytest.raises(RuntimeError):
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            await uow.sentences.add(
                Sentence(
                    id="u2",
                    text="rolled back",
                    speaker_id="sp1",
                    segment_id="seg1",
                )
            )
            raise RuntimeError("force rollback")

    async with session_factory() as session:
        gone = await SentenceRepository(session).get("u2")
        assert gone is None
