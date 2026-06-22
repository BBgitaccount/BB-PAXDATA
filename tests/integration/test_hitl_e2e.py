import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from bb_paxdata.application.domain.models.human_review import AgreementStatus
from bb_paxdata.application.services.calibration_service import CalibrationService
from bb_paxdata.application.services.few_shot_injector import FewShotInjector
from bb_paxdata.application.use_cases.submit_human_review import (
    SubmitHumanReviewCommand,
    SubmitHumanReviewUseCase,
)
from bb_paxdata.infrastructure.db import models as m
from bb_paxdata.infrastructure.db.base import Base
from bb_paxdata.infrastructure.db.repositories.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
async def session_factory() -> async_sessionmaker[AsyncSession]:
    # In-memory database setup for clean testing isolation
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
async def test_hitl_e2e_flow(session_factory):
    # 1. Seed database with required panel, speaker, segment, sentences, and AI analyses
    async with session_factory() as session:
        # Seed panel, speaker, segment
        session.add(m.File(file_id="p1", file_name="p1.txt", idempotency_key="p1_key"))
        session.add(m.SpeakerProfile(speaker_id="sp1", full_name="Expert speaker"))
        await session.flush()

        session.add(
            m.Segment(
                seg_id="seg1",
                file_id="p1",
                speaker_id="sp1",
                speaker_name="Expert speaker",
                text="Diplomatic statement",
            )
        )
        await session.flush()

        # Seed two sentences
        session.add(
            m.Sentence(
                sent_id="sent_01",
                seg_id="seg1",
                file_id="p1",
                speaker_id="sp1",
                speaker_name="Expert speaker",
                text="We want to cooperate with our neighbors.",
            )
        )
        session.add(
            m.Sentence(
                sent_id="sent_02",
                seg_id="seg1",
                file_id="p1",
                speaker_id="sp1",
                speaker_name="Expert speaker",
                text="We will retaliate against any aggression.",
            )
        )
        await session.flush()

        # Seed two AI analyses for these sentences (with a specific prompt version)
        prompt_ver = "sentence_analysis@v1.0"

        # Sentence 1: AI analyzed as COOPERATION (Frame) and LOW (Risk)
        session.add(
            m.AISentenceAnalysis(
                sent_id="sent_01",
                prompt_version=prompt_ver,
                framing="COOPERATION",
                risk_level=m.RiskLevel.LOW,
                sentiment_score=0.5,
            )
        )
        # Sentence 2: AI analyzed as COOPERATION (Frame) and LOW (Risk)
        session.add(
            m.AISentenceAnalysis(
                sent_id="sent_02",
                prompt_version=prompt_ver,
                framing="COOPERATION",
                risk_level=m.RiskLevel.LOW,
                sentiment_score=-0.2,
            )
        )
        await session.commit()

    # Create UOW factory pointing to our testing DB
    def uow_factory():
        return SqlAlchemyUnitOfWork(session_factory)

    # 2. Submit human reviews (one AGREED, one DISAGREED/corrected)
    submit_use_case = SubmitHumanReviewUseCase(uow_factory)

    # Review 1 (AGREED): Human agrees with the AI analysis of sentence 1
    cmd1 = SubmitHumanReviewCommand(
        analysis_id="sent_01",
        reviewer_id="reviewer_alpha",
        human_frame="COOPERATION",
        human_risk="LOW",
        human_sentiment=0.5,
        human_sbi=10.0,
        review_duration_seconds=15,
    )
    review1 = await submit_use_case.execute(cmd1)
    assert review1.agreement_status == AgreementStatus.AGREED
    assert review1.sentence_text == "We want to cooperate with our neighbors."

    # Review 2 (DISAGREED): Human disagrees and corrects sentence 2 (Frame: SECURITY, Risk: HIGH)
    cmd2 = SubmitHumanReviewCommand(
        analysis_id="sent_02",
        reviewer_id="reviewer_alpha",
        human_frame="SECURITY",
        human_risk="HIGH",
        human_sentiment=-0.5,
        human_sbi=45.0,
        disagreement_reason="Strong retaliation message detected.",
        review_duration_seconds=30,
    )
    review2 = await submit_use_case.execute(cmd2)
    assert review2.agreement_status == AgreementStatus.DISAGREED
    assert review2.sentence_text == "We will retaliate against any aggression."

    # Verify both exist in the DB
    async with session_factory() as session:
        from sqlalchemy import select

        from bb_paxdata.infrastructure.db.human_review_table import HumanReviewORM

        res = await session.execute(select(HumanReviewORM))
        rows = res.scalars().all()
        assert len(rows) == 2

    # 3. Run weekly calibration via CalibrationService
    calibration_service = CalibrationService(uow_factory)
    report = await calibration_service.run_weekly_calibration(
        prompt_version=prompt_ver, days_back=7
    )

    # Assert calculations are correct and run over all 2 reviews (not just the 1 disagreement)
    assert report.total_reviews == 2
    assert report.total_disagreements == 1
    assert report.disagreement_rate == pytest.approx(0.5)

    # Assert specific disagreement patterns are stored
    assert len(report.top_disagreement_patterns) == 1
    assert report.top_disagreement_patterns[0] == "Strong retaliation message detected."

    # 4. Run Few-Shot prompt injection and verify output format & sentence text
    few_shot_injector = FewShotInjector(uow_factory, enabled=True)
    base_prompt = "Analyze the diplomatic tone of the sentence."

    injected_prompt = await few_shot_injector.inject(
        base_prompt=base_prompt, frame_hint=None, n_examples=2
    )

    # Assert formatting contains the original sentence texts
    assert "UZMAN ONAYLI REFERANS ÖRNEKLER" in injected_prompt
    assert "We want to cooperate with our neighbors." in injected_prompt
    assert "We will retaliate against any aggression." in injected_prompt
    assert "Uzman Frame: SECURITY" in injected_prompt
    assert "Gerekçe: Strong retaliation message detected." in injected_prompt
