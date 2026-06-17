# tests/infrastructure/webhooks/test_outbox.py
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from bb_paxdata.infrastructure.db.base import Base
from bb_paxdata.infrastructure.db.models import (
    DomainEvent,
    OutboxEventORM,
    WebhookSubscriptionORM,
)
from bb_paxdata.infrastructure.events.publisher import WORMEventPublisher
from bb_paxdata.infrastructure.webhooks.tasks import (
    dispatch_webhook,
    process_outbox_queue,
)
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

# --- Async Tests for WORMEventPublisher ---


@pytest.mark.asyncio
async def test_worm_event_publisher_emits_outbox_for_matching_subscription():
    # 1. Setup async SQLite memory database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        # 2. Add subscriptions
        sub_matching = WebhookSubscriptionORM(
            id="sub-matching",
            endpoint_url="http://example.com/matching",
            secret="secret-matching",
            event_types=["AnalysisCompleted"],
            is_active=True,
        )
        sub_all = WebhookSubscriptionORM(
            id="sub-all",
            endpoint_url="http://example.com/all",
            secret="secret-all",
            event_types=["*"],
            is_active=True,
        )
        sub_other = WebhookSubscriptionORM(
            id="sub-other",
            endpoint_url="http://example.com/other",
            secret="secret-other",
            event_types=["OtherEvent"],
            is_active=True,
        )
        sub_inactive = WebhookSubscriptionORM(
            id="sub-inactive",
            endpoint_url="http://example.com/inactive",
            secret="secret-inactive",
            event_types=["*"],
            is_active=False,
        )
        session.add_all([sub_matching, sub_all, sub_other, sub_inactive])
        await session.commit()

        # 3. Emit event using publisher
        publisher = WORMEventPublisher(session)
        await publisher.emit(
            aggregate_type="AISentenceAnalysis",
            aggregate_id="sent-123",
            event_type="AnalysisCompleted",
            payload={"score": 0.95},
        )
        await session.commit()

        # 4. Assert that correct outbox events were generated
        outbox_stmt = select(OutboxEventORM).order_by(OutboxEventORM.endpoint_id)
        result = await session.execute(outbox_stmt)
        events = result.scalars().all()

        assert len(events) == 2
        # Event 1: sub-all
        assert events[0].endpoint_id == "sub-all"
        assert events[0].endpoint_url == "http://example.com/all"
        assert events[0].secret == "secret-all"
        assert events[0].payload == {"score": 0.95}

        # Event 2: sub-matching
        assert events[1].endpoint_id == "sub-matching"
        assert events[1].endpoint_url == "http://example.com/matching"
        assert events[1].secret == "secret-matching"
        assert events[1].payload == {"score": 0.95}

    await engine.dispose()


@pytest.mark.asyncio
async def test_worm_event_publisher_batch_emits_outbox():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        sub = WebhookSubscriptionORM(
            id="sub-1",
            endpoint_url="http://example.com/sub1",
            secret="sec-1",
            event_types=["EventA"],
            is_active=True,
        )
        session.add(sub)
        await session.commit()

        publisher = WORMEventPublisher(session)
        await publisher.emit_batch(
            [
                {
                    "aggregate_type": "TypeA",
                    "aggregate_id": "agg-1",
                    "event_type": "EventA",
                    "payload": {"data": "A"},
                },
                {
                    "aggregate_type": "TypeB",
                    "aggregate_id": "agg-2",
                    "event_type": "EventB",
                    "payload": {"data": "B"},
                },
            ]
        )
        await session.commit()

        # Check outbox events (only EventA should match)
        outbox_stmt = select(OutboxEventORM)
        result = await session.execute(outbox_stmt)
        events = result.scalars().all()

        assert len(events) == 1
        assert events[0].event_type == "EventA"
        assert events[0].endpoint_id == "sub-1"
        assert events[0].payload == {"data": "A"}

    await engine.dispose()


# --- Sync Tests for process_outbox_queue ---


@pytest.fixture
def sync_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with patch(
        "bb_paxdata.infrastructure.db.session.SessionLocalSync", TestingSessionLocal
    ):
        yield TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@patch("bb_paxdata.infrastructure.webhooks.tasks.dispatch_webhook.delay")
def test_process_outbox_queue_dispatches_pending_events(mock_dispatch, sync_db):
    session = sync_db()

    # 1. Create outbox events
    event_pending = OutboxEventORM(
        id="evt-pending",
        event_type="AnalysisCompleted",
        aggregate_id="agg-1",
        payload={"score": 0.8},
        endpoint_url="http://example.com/target",
        secret="mysecret",
        endpoint_id="sub-1",
        processed=False,
    )
    event_processed = OutboxEventORM(
        id="evt-processed",
        event_type="AnalysisCompleted",
        aggregate_id="agg-2",
        payload={"score": 0.9},
        endpoint_url="http://example.com/target",
        secret="mysecret",
        endpoint_id="sub-1",
        processed=True,
    )
    event_future = OutboxEventORM(
        id="evt-future",
        event_type="AnalysisCompleted",
        aggregate_id="agg-3",
        payload={"score": 0.7},
        endpoint_url="http://example.com/target",
        secret="mysecret",
        endpoint_id="sub-1",
        processed=False,
        next_attempt_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    session.add_all([event_pending, event_processed, event_future])
    session.commit()
    session.close()

    # 2. Run background queue processor task
    res = process_outbox_queue()

    assert res["dispatched_count"] == 1
    mock_dispatch.assert_called_once_with(
        event_id="evt-pending",
        endpoint_url="http://example.com/target",
        payload={"score": 0.8},
        secret="mysecret",
        endpoint_id="sub-1",
        event_version=1,
    )

    # 3. Verify event state in database (next_attempt_at should be updated to future lock time)
    session = sync_db()
    updated = session.get(OutboxEventORM, "evt-pending")
    assert updated.next_attempt_at is not None
    next_att = (
        updated.next_attempt_at.replace(tzinfo=None)
        if updated.next_attempt_at.tzinfo
        else updated.next_attempt_at
    )
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    assert (next_att - now_naive).total_seconds() > 0
    session.close()


@patch("bb_paxdata.infrastructure.webhooks.tasks.process_outbox_queue.delay")
def test_outbox_processing_triggered_after_commit(mock_process, sync_db):
    session = sync_db()
    event = OutboxEventORM(
        id="evt-trigger-test",
        event_type="test_event",
        aggregate_id="agg-test",
        payload={"foo": "bar"},
        processed=False,
    )
    session.add(event)
    session.commit()
    session.close()

    mock_process.assert_called_once()


def test_celery_task_routing():
    from bb_paxdata.infrastructure.tasks.celery_app import get_celery_app

    app = get_celery_app()
    routes = app.conf.task_routes
    assert routes["webhooks.process_outbox_queue"]["queue"] == "graph_io"
    assert routes["webhooks.dispatch"]["queue"] == "graph_io"


@patch("bb_paxdata.infrastructure.webhooks.tasks.httpx.Client")
@patch("bb_paxdata.infrastructure.webhooks.circuit_breaker.CircuitBreaker.is_allowed")
@patch(
    "bb_paxdata.infrastructure.webhooks.circuit_breaker.CircuitBreaker.record_success"
)
def test_circuit_breaker_integration_success(
    mock_record_success, mock_is_allowed, mock_client, sync_db
):
    mock_is_allowed.return_value = True

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_client.return_value.__enter__.return_value.post.return_value = mock_response

    session = sync_db()
    event = OutboxEventORM(
        id="evt-cb-success",
        event_type="test_event",
        aggregate_id="agg-cb",
        payload={"foo": "bar"},
        processed=False,
    )
    session.add(event)
    session.commit()
    session.close()

    res = dispatch_webhook.run(
        event_id="evt-cb-success",
        endpoint_url="http://example.com",
        payload={"foo": "bar"},
        secret="key",
        endpoint_id="ep-1",
    )

    assert res["status"] == "delivered"
    mock_is_allowed.assert_called_once()
    mock_record_success.assert_called_once()


@patch("bb_paxdata.infrastructure.webhooks.tasks.httpx.Client")
@patch("bb_paxdata.infrastructure.webhooks.circuit_breaker.CircuitBreaker.is_allowed")
def test_circuit_breaker_integration_open(mock_is_allowed, mock_client, sync_db):
    mock_is_allowed.return_value = False

    session = sync_db()
    event = OutboxEventORM(
        id="evt-cb-open",
        event_type="test_event",
        aggregate_id="agg-cb",
        payload={"foo": "bar"},
        processed=False,
    )
    session.add(event)
    session.commit()
    session.close()

    from celery.exceptions import Retry

    with pytest.raises((Retry, Exception)):
        dispatch_webhook.run(
            event_id="evt-cb-open",
            endpoint_url="http://example.com",
            payload={"foo": "bar"},
            secret="key",
            endpoint_id="ep-1",
        )

    # HTTP client post should NOT have been called
    assert not mock_client.return_value.__enter__.return_value.post.called


def test_event_upcaster_registry():
    from bb_paxdata.infrastructure.events.upcaster import EventUpcasterRegistry

    registry = EventUpcasterRegistry()

    # Check default
    assert registry.get_latest_version("TestEvent") == 1

    # Register V1 -> V2
    registry.register_upcaster("TestEvent", 1, 2, lambda p: {**p, "v2_field": True})
    assert registry.get_latest_version("TestEvent") == 2

    # Register V2 -> V3
    registry.register_upcaster("TestEvent", 2, 3, lambda p: {**p, "v3_field": True})
    assert registry.get_latest_version("TestEvent") == 3

    # Test upcast from V1 to V3
    payload = {"base": 42}
    upcasted, latest = registry.upcast("TestEvent", payload, current_version=1)

    assert latest == 3
    assert upcasted == {"base": 42, "v2_field": True, "v3_field": True}


@patch("bb_paxdata.infrastructure.webhooks.tasks.httpx.Client")
def test_dispatch_webhook_upcasts_and_includes_headers(mock_client, sync_db):
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_client.return_value.__enter__.return_value.post.return_value = mock_response

    # Seed an event at v1 (AnalysisCompleted)
    session = sync_db()
    event = OutboxEventORM(
        id="evt-upcast-test",
        event_type="AnalysisCompleted",
        event_version=1,
        aggregate_id="agg-upcast",
        payload={"sentiment_score": 0.85},
        processed=False,
    )
    session.add(event)
    session.commit()
    session.close()

    res = dispatch_webhook.run(
        event_id="evt-upcast-test",
        endpoint_url="http://example.com/target",
        payload={"sentiment_score": 0.85},
        secret="key",
        endpoint_id="ep-1",
        event_version=1,
    )

    assert res["status"] == "delivered"

    # Verify httpx client was called with upcasted payload and headers
    post_args, post_kwargs = (
        mock_client.return_value.__enter__.return_value.post.call_args
    )
    assert post_args[0] == "http://example.com/target"

    # Payload should be upcasted (sentiment_score -> ai_sentiment_score, coherence_score added)
    sent_json = post_kwargs["json"]
    assert "sentiment_score" not in sent_json
    assert sent_json["ai_sentiment_score"] == 0.85
    assert sent_json["coherence_score"] == 1.0

    # Headers should include version and type
    sent_headers = post_kwargs["headers"]
    assert sent_headers["X-Paxdata-Event-Id"] == "evt-upcast-test"
    assert sent_headers["X-Paxdata-Event-Type"] == "AnalysisCompleted"
    assert sent_headers["X-Paxdata-Event-Version"] == "2"


@pytest.mark.asyncio
async def test_worm_event_publisher_uses_latest_registry_version():
    from bb_paxdata.infrastructure.events.upcaster import global_upcaster_registry

    # 1. Setup async SQLite memory database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        # Add active subscription
        sub = WebhookSubscriptionORM(
            id="sub-ver-test",
            endpoint_url="http://example.com/webhook",
            secret="supersecret",
            event_types=["AnalysisCompleted"],
            is_active=True,
        )
        session.add(sub)
        await session.commit()

        # Emit event
        publisher = WORMEventPublisher(session)
        await publisher.emit(
            aggregate_type="AISentenceAnalysis",
            aggregate_id="sent-abc",
            event_type="AnalysisCompleted",
            payload={"sentiment_score": 0.5},
        )
        await session.commit()

        # Retrieve DomainEvent and OutboxEventORM from database
        de_stmt = select(DomainEvent).where(DomainEvent.aggregate_id == "sent-abc")
        de_res = await session.execute(de_stmt)
        domain_event = de_res.scalar_one_or_none()

        oe_stmt = select(OutboxEventORM).where(
            OutboxEventORM.aggregate_id == "sent-abc"
        )
        oe_res = await session.execute(oe_stmt)
        outbox_event = oe_res.scalar_one_or_none()

        latest_expected = global_upcaster_registry.get_latest_version(
            "AnalysisCompleted"
        )

        assert domain_event is not None
        assert domain_event.event_version == latest_expected

        assert outbox_event is not None
        assert outbox_event.event_version == latest_expected

    await engine.dispose()
