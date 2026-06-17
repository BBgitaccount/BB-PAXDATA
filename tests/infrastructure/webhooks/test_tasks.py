# tests/infrastructure/webhooks/test_tasks.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from bb_paxdata.infrastructure.db.base import Base
from bb_paxdata.infrastructure.db.models import DeadLetterEventORM, OutboxEventORM
from bb_paxdata.infrastructure.webhooks.tasks import (
    _acquire_lease,
    _release_lease_for_retry,
    dispatch_webhook,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def sync_db():
    # Setup temporary SQLite database
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Patch the SessionLocalSync inside session.py
    with patch(
        "bb_paxdata.infrastructure.db.session.SessionLocalSync", TestingSessionLocal
    ):
        yield TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_acquire_lease_success(sync_db):
    session = sync_db()
    event = OutboxEventORM(
        id="evt-123",
        event_type="test_event",
        aggregate_id="agg-123",
        payload={"foo": "bar"},
        processed=False,
    )
    session.add(event)
    session.commit()
    session.close()

    # Should successfully acquire lease
    assert _acquire_lease("evt-123") is True

    # Check database state
    session = sync_db()
    updated_event = session.get(OutboxEventORM, "evt-123")
    assert updated_event.attempts == 1
    assert updated_event.last_attempt_at is not None
    session.close()


def test_acquire_lease_already_leased(sync_db):
    session = sync_db()
    event = OutboxEventORM(
        id="evt-123",
        event_type="test_event",
        aggregate_id="agg-123",
        payload={"foo": "bar"},
        processed=False,
        last_attempt_at=datetime.now(timezone.utc),
        attempts=1,
    )
    session.add(event)
    session.commit()
    session.close()

    # Second acquisition attempt within lease duration (60s) should fail
    assert _acquire_lease("evt-123") is False


def test_acquire_lease_expired(sync_db):
    session = sync_db()
    expired_time = datetime.now(timezone.utc) - timedelta(seconds=70)
    event = OutboxEventORM(
        id="evt-123",
        event_type="test_event",
        aggregate_id="agg-123",
        payload={"foo": "bar"},
        processed=False,
        last_attempt_at=expired_time,
        attempts=1,
    )
    session.add(event)
    session.commit()
    session.close()

    # Should successfully acquire lease since 70s > 60s
    assert _acquire_lease("evt-123") is True


def test_acquire_lease_already_processed(sync_db):
    session = sync_db()
    event = OutboxEventORM(
        id="evt-123",
        event_type="test_event",
        aggregate_id="agg-123",
        payload={"foo": "bar"},
        processed=True,
    )
    session.add(event)
    session.commit()
    session.close()

    # Should fail because it is already processed
    assert _acquire_lease("evt-123") is False


def test_release_lease_for_retry(sync_db):
    session = sync_db()
    event = OutboxEventORM(
        id="evt-123",
        event_type="test_event",
        aggregate_id="agg-123",
        payload={"foo": "bar"},
        processed=False,
        last_attempt_at=datetime.now(timezone.utc),
        attempts=1,
    )
    session.add(event)
    session.commit()
    session.close()

    _release_lease_for_retry("evt-123", countdown=15.0)

    session = sync_db()
    updated = session.get(OutboxEventORM, "evt-123")
    assert updated.last_attempt_at is None
    assert updated.next_attempt_at is not None
    session.close()


@patch("bb_paxdata.infrastructure.webhooks.tasks.httpx.Client")
def test_dispatch_webhook_success(mock_client, sync_db):
    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.status_code = 200
    mock_client.return_value.__enter__.return_value.post.return_value = mock_response

    # Seed event
    session = sync_db()
    event = OutboxEventORM(
        id="evt-123",
        event_type="test_event",
        aggregate_id="agg-123",
        payload={"foo": "bar"},
        processed=False,
    )
    session.add(event)
    session.commit()
    session.close()

    # Run dispatch using .run to bypass Celery Bind proxy
    res = dispatch_webhook.run(
        event_id="evt-123",
        endpoint_url="http://example.com",
        payload={"foo": "bar"},
        secret="key",
        endpoint_id="ep-1",
    )

    assert res["status"] == "delivered"

    # Verify database was updated
    session = sync_db()
    updated = session.get(OutboxEventORM, "evt-123")
    assert updated.processed is True
    session.close()


@patch("bb_paxdata.infrastructure.webhooks.tasks.httpx.Client")
def test_dispatch_webhook_skipped_concurrent(mock_client, sync_db):
    # Seed event already leased (simulate concurrent worker)
    session = sync_db()
    event = OutboxEventORM(
        id="evt-123",
        event_type="test_event",
        aggregate_id="agg-123",
        payload={"foo": "bar"},
        processed=False,
        last_attempt_at=datetime.now(timezone.utc),
        attempts=1,
    )
    session.add(event)
    session.commit()
    session.close()

    # Run dispatch using .run to bypass Celery Bind proxy
    res = dispatch_webhook.run(
        event_id="evt-123",
        endpoint_url="http://example.com",
        payload={"foo": "bar"},
        secret="key",
        endpoint_id="ep-1",
    )

    assert res["status"] == "skipped"
    # HTTP post should not have been called
    assert not mock_client.return_value.__enter__.return_value.post.called


def test_dead_letter_resolved_deletes_outbox_event(sync_db):
    session = sync_db()
    # 1. Create an outbox event
    outbox = OutboxEventORM(
        id="evt-abc",
        event_type="test_event",
        aggregate_id="agg-abc",
        payload={"data": 123},
        processed=True,
    )
    session.add(outbox)
    session.commit()

    # 2. Create a dead letter event for it
    dead = DeadLetterEventORM(
        original_event_id="evt-abc",
        event_type="test_event",
        payload={"data": 123},
        failure_reason="Some error",
        resolved=False,
    )
    session.add(dead)
    session.commit()

    # Verify both exist
    assert session.get(OutboxEventORM, "evt-abc") is not None
    assert session.get(DeadLetterEventORM, dead.id) is not None

    # 3. Mark the dead letter event as resolved
    dead.resolved = True
    session.commit()

    # 4. Verify outbox event is deleted
    assert session.get(OutboxEventORM, "evt-abc") is None
    # And dead letter event still exists and is resolved
    session.expire(dead)
    resolved_dead = session.get(DeadLetterEventORM, dead.id)
    assert resolved_dead is not None
    assert resolved_dead.resolved is True
    session.close()


def test_dead_letter_created_resolved_deletes_outbox_event(sync_db):
    session = sync_db()
    outbox = OutboxEventORM(
        id="evt-xyz",
        event_type="test_event",
        aggregate_id="agg-xyz",
        payload={"data": 123},
        processed=True,
    )
    session.add(outbox)
    session.commit()

    # Create resolved dead letter event directly
    dead = DeadLetterEventORM(
        original_event_id="evt-xyz",
        event_type="test_event",
        payload={"data": 123},
        failure_reason="Some error",
        resolved=True,
    )
    session.add(dead)
    session.commit()

    assert session.get(OutboxEventORM, "evt-xyz") is None
    assert session.get(DeadLetterEventORM, dead.id) is not None
    session.close()
