# src/bb_paxdata/infrastructure/webhooks/tasks.py
from __future__ import annotations

import random

import httpx
from celery import Task
from celery.utils.log import get_task_logger

from bb_paxdata.infrastructure.tasks.celery_app import get_celery_app
from bb_paxdata.infrastructure.webhooks.signature import generate_webhook_signature

celery_app = get_celery_app()

logger = get_task_logger(__name__)

MAX_RETRIES = 7
BASE_DELAY_SECONDS = 10
JITTER_RANGE = (0.0, 5.0)  # Thundering herd önleme


def _compute_backoff(attempt: int) -> float:
    """
    Delay = 2^attempt × BASE + Uniform(JITTER_RANGE[0], JITTER_RANGE[1])
    Attempt 0: ~10s, 1: ~20s, 2: ~40s, ..., 6: ~640s
    """
    delay = (2**attempt) * BASE_DELAY_SECONDS
    jitter = random.uniform(*JITTER_RANGE)
    return round(delay + jitter, 2)


@celery_app.task(
    bind=True,
    name="webhooks.dispatch",
    max_retries=MAX_RETRIES,
    acks_late=True,  # Task ACK'i işlem bittikten sonra gönder (worker crash koruması)
    reject_on_worker_lost=True,
)
def dispatch_webhook(
    self: Task,
    event_id: str,
    endpoint_url: str,
    payload: dict,
    secret: str,
    endpoint_id: str,
    event_version: int | None = None,
) -> dict:
    """
    Webhook isteğini gönderir. Başarısızlıkta exponential backoff ile tekrar dener.
    MaxRetry aşımında event dead_letter_events tablosuna taşınır.
    """
    # 1. Acquire lease first to prevent concurrent execution by other workers
    if not _acquire_lease(event_id):
        logger.info(
            "Webhook dispatch skipped: event already processed or currently leased by another worker. event_id=%s",
            event_id,
        )
        return {"status": "skipped"}

    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    cb = None
    redis_client = None
    cb_allowed = True
    try:
        import redis.asyncio as aioredis

        from bb_paxdata.config.settings import get_settings
        from bb_paxdata.infrastructure.webhooks.circuit_breaker import CircuitBreaker

        settings = get_settings()
        if settings.redis_url:
            redis_client = aioredis.Redis.from_url(settings.redis_url)
            cb = CircuitBreaker(redis_client, endpoint_id)
            cb_allowed = loop.run_until_complete(cb.is_allowed())
    except Exception as e:
        logger.warning(
            "Circuit breaker check failed or Redis not available: %s. Defaulting to allowed.",
            str(e),
        )

    if not cb_allowed:
        logger.warning(
            "Webhook dispatch skipped: Circuit breaker is OPEN. endpoint_id=%s, event_id=%s",
            endpoint_id,
            event_id,
        )
        _release_lease_for_retry(event_id, 60.0)
        if redis_client:
            try:
                loop.run_until_complete(redis_client.close())
            except Exception:
                pass
        raise self.retry(
            exc=Exception(f"Circuit breaker is OPEN for endpoint {endpoint_id}"),
            countdown=60.0,
        )

    # 2. Resolve event version and type, then upcast the payload if needed
    from bb_paxdata.infrastructure.db.models import OutboxEventORM
    from bb_paxdata.infrastructure.db.session import get_db_session
    from bb_paxdata.infrastructure.events.upcaster import global_upcaster_registry

    version = event_version
    event_type = "unknown"

    with get_db_session() as session:
        evt_orm = (
            session.query(OutboxEventORM).filter(OutboxEventORM.id == event_id).first()
        )
        if evt_orm:
            event_type = evt_orm.event_type
            if version is None:
                version = getattr(evt_orm, "event_version", 1)

    if version is None:
        version = 1

    upcasted_payload, latest_version = global_upcaster_registry.upcast(
        event_type=event_type,
        payload=payload,
        current_version=version,
    )

    signature_header, _ = generate_webhook_signature(upcasted_payload, secret)

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                endpoint_url,
                json=upcasted_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Paxdata-Signature": signature_header,
                    "X-Paxdata-Event-Id": event_id,
                    "X-Paxdata-Event-Type": event_type,
                    "X-Paxdata-Event-Version": str(latest_version),
                    "User-Agent": "BB-PAXDATA-Webhook/1.0",
                },
            )

        # 2xx: başarılı
        if response.is_success:
            _mark_event_processed(event_id)
            logger.info(
                "Webhook dispatched. event_id=%s status=%s",
                event_id,
                response.status_code,
            )
            if cb:
                try:
                    loop.run_until_complete(cb.record_success())
                except Exception as e:
                    logger.warning("Failed to record circuit breaker success: %s", e)
            if redis_client:
                try:
                    loop.run_until_complete(redis_client.close())
                except Exception:
                    pass
            return {"status": "delivered", "http_status": response.status_code}

        # 4xx: kalıcı hata, tekrar deneme anlamsız
        if 400 <= response.status_code < 500:
            logger.error(
                "Permanent webhook failure (4xx). event_id=%s status=%s",
                event_id,
                response.status_code,
            )
            _move_to_dead_letter(
                event_id, payload, f"HTTP {response.status_code}: {response.text[:500]}"
            )
            if redis_client:
                try:
                    loop.run_until_complete(redis_client.close())
                except Exception:
                    pass
            return {"status": "permanent_failure", "http_status": response.status_code}

        # 5xx: geçici hata, retry
        raise httpx.HTTPStatusError(
            f"Server error {response.status_code}",
            request=response.request,
            response=response,
        )

    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        if cb:
            try:
                loop.run_until_complete(cb.record_failure())
            except Exception as e:
                logger.warning("Failed to record circuit breaker failure: %s", e)
        if redis_client:
            try:
                loop.run_until_complete(redis_client.close())
            except Exception:
                pass

        attempt = self.request.retries
        if attempt >= MAX_RETRIES:
            _move_to_dead_letter(event_id, payload, str(exc))
            logger.error("Max retries exceeded. event_id=%s", event_id, exc_info=True)
            return {"status": "dead_letter"}

        countdown = _compute_backoff(attempt)
        logger.warning(
            "Webhook retry %d/%d in %.1fs. event_id=%s error=%s",
            attempt + 1,
            MAX_RETRIES,
            countdown,
            event_id,
            str(exc),
        )
        _release_lease_for_retry(event_id, countdown)
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        from celery.exceptions import Retry

        if isinstance(exc, Retry):
            raise
        if redis_client:
            try:
                loop.run_until_complete(redis_client.close())
            except Exception:
                pass
        # Unexpected error: release lease to avoid locking the event for 60s
        _release_lease_for_retry(event_id, 0)
        raise


LEASE_DURATION_SECONDS = 60


def _acquire_lease(event_id: str) -> bool:
    """
    Acquire a short-lived lock (lease) on the event to prevent concurrent processing.
    Returns True if lease acquired successfully, False if already processed or leased.
    """
    from datetime import datetime, timezone

    from bb_paxdata.infrastructure.db.models import OutboxEventORM
    from bb_paxdata.infrastructure.db.session import get_db_session

    with get_db_session() as session:
        # SELECT ... FOR UPDATE to prevent race conditions during check-and-lease
        event = (
            session.query(OutboxEventORM)
            .filter(OutboxEventORM.id == event_id)
            .with_for_update()
            .first()
        )
        if not event:
            return False

        if event.processed:
            return False

        now = datetime.now(timezone.utc)
        if event.last_attempt_at is not None:
            last_attempt = event.last_attempt_at
            if last_attempt.tzinfo is None:
                last_attempt = last_attempt.replace(tzinfo=timezone.utc)
            time_since_attempt = (now - last_attempt).total_seconds()
            if time_since_attempt < LEASE_DURATION_SECONDS:
                # Still leased by another worker
                return False

        # Acquire/renew lease
        event.last_attempt_at = now
        event.attempts += 1
        session.commit()
        return True


def _release_lease_for_retry(event_id: str, countdown: float) -> None:
    """
    Clear the lease so that a scheduled retry task can run without waiting
    for the lease duration to expire.
    """
    from datetime import datetime, timedelta, timezone

    from bb_paxdata.infrastructure.db.models import OutboxEventORM
    from bb_paxdata.infrastructure.db.session import get_db_session

    with get_db_session() as session:
        event = (
            session.query(OutboxEventORM)
            .filter(OutboxEventORM.id == event_id)
            .with_for_update()
            .first()
        )
        if event:
            event.last_attempt_at = None
            if countdown > 0:
                event.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                    seconds=countdown
                )
            session.commit()


def _mark_event_processed(event_id: str) -> None:
    """OutboxEvent'i processed=True olarak günceller."""
    from datetime import datetime, timezone

    from bb_paxdata.infrastructure.db.models import OutboxEventORM
    from bb_paxdata.infrastructure.db.session import get_db_session

    with get_db_session() as session:
        event = (
            session.query(OutboxEventORM)
            .filter(OutboxEventORM.id == event_id)
            .with_for_update()
            .first()
        )
        if event:
            event.processed = True
            event.last_attempt_at = datetime.now(timezone.utc)
            session.commit()


def _move_to_dead_letter(event_id: str, payload: dict, reason: str) -> None:
    """Event'i dead_letter_events tablosuna taşır."""
    from bb_paxdata.infrastructure.db.models import (
        DeadLetterEventORM,
        OutboxEventORM,
    )
    from bb_paxdata.infrastructure.db.session import get_db_session

    with get_db_session() as session:
        original = (
            session.query(OutboxEventORM)
            .filter(OutboxEventORM.id == event_id)
            .with_for_update()
            .first()
        )
        if original:
            dead = DeadLetterEventORM(
                original_event_id=event_id,
                event_type=original.event_type,
                event_version=getattr(original, "event_version", 1),
                payload=payload,
                failure_reason=reason,
            )
            session.add(dead)
            original.processed = True  # outbox'tan temizle
            session.commit()


@celery_app.task(name="webhooks.process_outbox_queue")
def process_outbox_queue() -> dict:
    """
    Polls the database for unprocessed OutboxEventORM records and dispatches them via Celery.
    """
    from datetime import datetime, timedelta, timezone

    from bb_paxdata.infrastructure.db.models import OutboxEventORM
    from bb_paxdata.infrastructure.db.session import get_db_session

    now = datetime.now(timezone.utc)

    with get_db_session() as session:
        # Query pending events that are ready to run
        pending_events = (
            session.query(OutboxEventORM)
            .filter(
                not OutboxEventORM.processed,
                (OutboxEventORM.next_attempt_at is None)
                | (OutboxEventORM.next_attempt_at <= now),
            )
            .limit(100)
            .all()
        )

        if not pending_events:
            return {"dispatched_count": 0}

        dispatched_count = 0
        for event in pending_events:
            # Set next_attempt_at to a future time to prevent subsequent sweeper runs
            # from picking it up before the worker starts processing it.
            event.next_attempt_at = now + timedelta(seconds=60)

            # Dispatch the celery task
            dispatch_webhook.delay(
                event_id=event.id,
                endpoint_url=event.endpoint_url,
                payload=event.payload,
                secret=event.secret,
                endpoint_id=event.endpoint_id,
                event_version=getattr(event, "event_version", 1),
            )
            dispatched_count += 1

        session.commit()
        logger.info("Dispatched %d outbox events to Celery", dispatched_count)
        return {"dispatched_count": dispatched_count}
