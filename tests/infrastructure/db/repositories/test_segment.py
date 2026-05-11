"""Tests for ``SegmentRepository``."""

from __future__ import annotations

from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.db.repositories.segment import SegmentRepository
from bb_paxdata.infrastructure.db.repositories.sentence import SentenceRepository

from tests.infrastructure.db.repositories.conftest import seed_panel_speaker_segment


async def test_segment_repo_get_with_sentences_eager(db_session) -> None:
    await seed_panel_speaker_segment(db_session)
    srepo = SentenceRepository(db_session)
    await srepo.add(Sentence(id="sx1", text="one", speaker_id="sp1", segment_id="seg1"))
    await srepo.add(Sentence(id="sx2", text="two", speaker_id="sp1", segment_id="seg1"))
    await db_session.commit()

    seg_repo = SegmentRepository(db_session)
    loaded = await seg_repo.get_with_sentences("seg1")
    assert loaded is not None
    assert loaded.id == "seg1"
    assert len(loaded.sentences) == 2
    texts = {s.text for s in loaded.sentences}
    assert texts == {"one", "two"}


async def test_segment_repo_temporal_analysis(db_session) -> None:
    await seed_panel_speaker_segment(db_session)
    from bb_paxdata.infrastructure.db import models as m

    seg = await db_session.get(m.Segment, "seg1")
    assert seg is not None
    seg.intro_sentiment = 0.1
    seg.develop_sentiment = 0.2
    seg.concl_sentiment = 0.3
    seg.risk_trend = "up"
    await db_session.commit()

    seg_repo = SegmentRepository(db_session)
    ta = await seg_repo.get_temporal_analysis("seg1")
    assert ta is not None
    assert ta.intro_sentiment == 0.1
    assert ta.develop_sentiment == 0.2
    assert ta.concl_sentiment == 0.3
    assert ta.risk_trend == "up"


async def test_segment_add_many(db_session) -> None:
    await seed_panel_speaker_segment(db_session)
    repo = SegmentRepository(db_session)
    segs = [
        Segment(id="g2", panel_id="p1", sentence_count=0, word_count=0),
        Segment(id="g3", panel_id="p1", sentence_count=0, word_count=0),
    ]
    await repo.add_many(segs)
    await db_session.commit()
    assert await repo.get("g2") is not None
    assert await repo.get("g3") is not None
