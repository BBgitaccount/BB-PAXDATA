"""Tests for ``SentenceRepository``."""

from __future__ import annotations

from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.db.repositories.sentence_repo import SentenceRepository

from tests.infrastructure.db.repositories.conftest import seed_panel_speaker_segment


def test_sentence_repo_add_and_get(db_session) -> None:
    seed_panel_speaker_segment(db_session)
    repo = SentenceRepository(db_session)
    sentence = Sentence(
        id="s1",
        text="We want peace.",
        speaker_id="sp1",
        segment_id="seg1",
    )
    repo.add(sentence)
    db_session.commit()

    result = repo.get("s1")
    assert result is not None
    assert result.text == "We want peace."
    assert result.segment_id == "seg1"


def test_sentence_repo_get_high_risk(db_session) -> None:
    seed_panel_speaker_segment(db_session)
    repo = SentenceRepository(db_session)
    low = Sentence(id="s_low", text="a", speaker_id="sp1", segment_id="seg1")
    high = Sentence(id="s_high", text="b", speaker_id="sp1", segment_id="seg1")
    repo.add(low)
    repo.add(high)
    db_session.flush()
    repo.update_analysis(
        "s_low",
        sentiment_score=0.0,
        risk_score=2,
        hedging_score=0.0,
        politeness_ratio=0.5,
    )
    repo.update_analysis(
        "s_high",
        sentiment_score=0.0,
        risk_score=8,
        hedging_score=0.0,
        politeness_ratio=0.5,
    )
    db_session.commit()

    high_risk = repo.get_high_risk(min_risk_score=7)
    assert len(high_risk) == 1
    assert high_risk[0].id == "s_high"
