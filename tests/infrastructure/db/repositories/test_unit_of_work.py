"""Unit of Work transaction behaviour."""

from __future__ import annotations

import pytest
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.db.repositories.sentence_repo import SentenceRepository
from bb_paxdata.infrastructure.db.repositories.unit_of_work import SqlAlchemyUnitOfWork

from tests.infrastructure.db.repositories.conftest import seed_panel_speaker_segment


def test_uow_commits_on_success(session_factory) -> None:
    seed_panel_speaker_segment(session_factory())
    uow = SqlAlchemyUnitOfWork(session_factory)
    with uow:
        uow.sentences.add(
            Sentence(id="u1", text="committed", speaker_id="sp1", segment_id="seg1")
        )
    check = SentenceRepository(session_factory()).get("u1")
    assert check is not None
    assert check.text == "committed"


def test_uow_rollbacks_on_exception(session_factory) -> None:
    seed_panel_speaker_segment(session_factory())
    with pytest.raises(RuntimeError):
        with SqlAlchemyUnitOfWork(session_factory) as uow:
            uow.sentences.add(
                Sentence(
                    id="u2",
                    text="rolled back",
                    speaker_id="sp1",
                    segment_id="seg1",
                )
            )
            raise RuntimeError("force rollback")

    gone = SentenceRepository(session_factory()).get("u2")
    assert gone is None
