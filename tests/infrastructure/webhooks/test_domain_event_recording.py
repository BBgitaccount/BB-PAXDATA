# tests/infrastructure/webhooks/test_domain_event_recording.py
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.infrastructure.db.base import Base
from bb_paxdata.infrastructure.db.models import (
    AISentenceAnalysis,
    DomainEvent,
    FormulaValidationLog,
    OutboxEventORM,
    Sentence,
    WebhookSubscriptionORM,
)


@pytest.mark.asyncio
async def test_domain_model_records_event():
    # 1. Instantiate the domain model
    analysis = Analysis(sentence_id="sent-123", sentiment_score=0.75)

    # 2. Verify events list is initially empty
    assert len(analysis.get_events()) == 0

    # 3. Record an event
    analysis.record_event(
        event_type="AnalysisCompleted",
        payload={"score": 0.75, "topic": "test"},
        actor_id="system",
        aggregate_id="sent-123",
    )

    # 4. Verify the event is recorded
    events = analysis.get_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "AnalysisCompleted"
    assert events[0]["payload"] == {"score": 0.75, "topic": "test"}
    assert events[0]["aggregate_type"] == "Analysis"
    assert events[0]["aggregate_id"] == "sent-123"
    assert events[0]["actor_id"] == "system"

    # 5. Clear events
    analysis.clear_events()
    assert len(analysis.get_events()) == 0


@pytest.mark.asyncio
async def test_orm_from_domain_transfers_events():
    # 1. Instantiate the domain model and record an event
    analysis = Analysis(sentence_id="sent-123", sentiment_score=0.75)
    analysis.record_event(
        event_type="AnalysisCompleted",
        payload={"score": 0.75},
        actor_id="system",
        aggregate_id="sent-123",
    )

    # 2. Map from domain to ORM instance (should trigger init subclass wrapper)
    orm_instance = AISentenceAnalysis.from_domain(
        analysis,
        sent_id="sent-123",
    )

    # 3. Verify that events are cleared on the domain model
    assert len(analysis.get_events()) == 0

    # 4. Verify that events are transferred to the ORM instance
    assert hasattr(orm_instance, "_domain_events")
    assert len(orm_instance._domain_events) == 1
    assert orm_instance._domain_events[0]["event_type"] == "AnalysisCompleted"
    assert orm_instance._domain_events[0]["aggregate_id"] == "sent-123"


@pytest.mark.asyncio
async def test_session_before_flush_hook_persists_events():
    # 1. Setup async SQLite memory database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        # 2. Add a subscription
        sub = WebhookSubscriptionORM(
            id="sub-123",
            endpoint_url="http://example.com/webhook",
            secret="supersecret",
            event_types=["AnalysisCompleted"],
            is_active=True,
        )
        session.add(sub)
        await session.commit()

        # 3. Add necessary parent row (Sentence) to satisfy ForeignKey sent_id
        db_sent = Sentence(
            sent_id="sent-123",
            sentence_code="S-1",
            text="Test sentence",
            word_count=2,
            char_count=13,
            seg_id="dummy-seg",
            file_id="dummy-file",
            speaker_name="dummy-speaker",
        )
        session.add(db_sent)
        await session.flush()

        # 4. Map a domain model with event to ORM instance
        analysis = Analysis(sentence_id="sent-123", sentiment_score=0.75)
        analysis.record_event(
            event_type="AnalysisCompleted",
            payload={"score": 0.75},
            actor_id="system",
            aggregate_id="sent-123",
        )

        orm_instance = AISentenceAnalysis.from_domain(
            analysis,
            sent_id="sent-123",
        )

        # 5. Add to session and flush
        session.add(orm_instance)
        await session.flush()

        # 6. Verify that DomainEvent was persisted
        de_stmt = select(DomainEvent).where(DomainEvent.aggregate_id == "sent-123")
        de_res = await session.execute(de_stmt)
        domain_event = de_res.scalar_one_or_none()
        assert domain_event is not None
        assert domain_event.event_type == "AnalysisCompleted"
        assert domain_event.payload == {"score": 0.75}

        # 7. Verify that OutboxEventORM was created
        oe_stmt = select(OutboxEventORM).where(
            OutboxEventORM.aggregate_id == "sent-123"
        )
        oe_res = await session.execute(oe_stmt)
        outbox_event = oe_res.scalar_one_or_none()
        assert outbox_event is not None
        assert outbox_event.event_type == "AnalysisCompleted"
        assert outbox_event.payload == {"score": 0.75}
        assert outbox_event.endpoint_url == "http://example.com/webhook"

    await engine.dispose()


@pytest.mark.asyncio
async def test_orm_record_event_directly_persists_events():
    # 1. Setup async SQLite memory database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        # 2. Add a subscription for FormulaValidated
        sub = WebhookSubscriptionORM(
            id="sub-456",
            endpoint_url="http://example.com/formula-webhook",
            secret="formula-secret",
            event_types=["FormulaValidated"],
            is_active=True,
        )
        session.add(sub)
        await session.commit()

        # 3. Create a FormulaValidationLog ORM instance and record an event directly on it
        db_log = FormulaValidationLog(
            run_id="run-1",
            entity_type="sentence",
            entity_id="sent-123",
            formula_name="test_formula",
            expected_constraint="value > 0",
            actual_value=1.5,
            status="PASS",
            details="Validation passed successfully",
            log_version=1,
            is_current=True,
        )

        session.add(db_log)

        # Record the event directly
        db_log.record_event(
            event_type="FormulaValidated",
            payload={"run_id": "run-1", "status": "PASS"},
            actor_id="system",
            aggregate_id="run-1_test_formula_sent-123",
        )

        # Flush the session
        await session.flush()

        # 4. Verify that DomainEvent was persisted
        de_stmt = select(DomainEvent).where(
            DomainEvent.aggregate_id == "run-1_test_formula_sent-123"
        )
        de_res = await session.execute(de_stmt)
        domain_event = de_res.scalar_one_or_none()
        assert domain_event is not None
        assert domain_event.event_type == "FormulaValidated"
        assert domain_event.payload == {"run_id": "run-1", "status": "PASS"}

        # 5. Verify that OutboxEventORM was created
        oe_stmt = select(OutboxEventORM).where(
            OutboxEventORM.aggregate_id == "run-1_test_formula_sent-123"
        )
        oe_res = await session.execute(oe_stmt)
        outbox_event = oe_res.scalar_one_or_none()
        assert outbox_event is not None
        assert outbox_event.event_type == "FormulaValidated"
        assert outbox_event.payload == {"run_id": "run-1", "status": "PASS"}
        assert outbox_event.endpoint_url == "http://example.com/formula-webhook"

    await engine.dispose()
