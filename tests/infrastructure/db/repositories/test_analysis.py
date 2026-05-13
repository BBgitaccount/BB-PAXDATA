"""Tests for ``AnalysisRepository``."""

from __future__ import annotations

from bb_paxdata.domain.enums import RiskLevel
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.domain.models.sentence import Sentence
from bb_paxdata.domain.models.validation_result import ValidationResult
from bb_paxdata.infrastructure.db import models as m
from bb_paxdata.infrastructure.db.repositories.analysis import AnalysisRepository
from bb_paxdata.infrastructure.db.repositories.sentence import SentenceRepository
from sqlalchemy.ext.asyncio import AsyncSession

from tests.infrastructure.db.repositories.conftest import seed_panel_speaker_segment


async def _seed_sentence(session: AsyncSession) -> None:
    await seed_panel_speaker_segment(session)
    await SentenceRepository(session).add(
        Sentence(id="s1", text="x", speaker_id="sp1", segment_id="seg1")
    )
    await session.commit()


async def test_analysis_save_and_get_sentence_analysis(
    db_session: AsyncSession,
) -> None:
    await _seed_sentence(db_session)
    repo = AnalysisRepository(db_session)
    analysis = Analysis(
        id="a1",
        sentence_id="s1",
        segment_id="seg1",
        risk_level=RiskLevel.HIGH,
        sentiment_score=-0.2,
        confidence_score=0.9,
    )
    await repo.save_sentence_analysis(analysis)
    await db_session.commit()

    loaded = await repo.get_sentence_analysis("s1")
    assert loaded is not None
    assert loaded.sentence_id == "s1"
    assert loaded.risk_level == RiskLevel.HIGH


async def test_analysis_get_failures(db_session: AsyncSession) -> None:
    await _seed_sentence(db_session)
    db_session.add(
        m.AISentenceAnalysis(
            sent_id="s1",
            panel_id="p1",
            overall_logic_check="FAIL",
            risk_level="HIGH",
            sentiment_score=0.0,
            has_demand=False,
            has_inconsistency=False,
            logic_pass_count=0,
            logic_fail_count=1,
            from_cache=False,
            prompt_version="v1",
        )
    )
    await db_session.commit()
    repo = AnalysisRepository(db_session)
    fails = await repo.get_failures(panel_id="p1")
    assert len(fails) >= 1


async def test_analysis_cache_roundtrip(db_session: AsyncSession) -> None:
    repo = AnalysisRepository(db_session)
    await repo.set_cache("h1", '{"x":1}', "m1", "b1")
    await db_session.commit()
    meta = await repo.get_cache("h1")
    assert meta is not None
    assert meta.entity_id == "h1"


async def test_validation_log_roundtrip(db_session: AsyncSession) -> None:
    await _seed_sentence(db_session)
    repo = AnalysisRepository(db_session)
    vr = ValidationResult(
        id="v1",
        entity_id="s1",
        entity_type="sentence",
        overall_status="passed",
        total_checks=1,
        passed_checks=1,
        failed_checks=0,
    )
    await repo.save_validation_log(vr)
    await db_session.commit()
    logs = await repo.get_validation_log("s1")
    assert len(logs) == 1
