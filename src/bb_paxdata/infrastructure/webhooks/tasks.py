# src/bb_paxdata/infrastructure/webhooks/tasks.py
from __future__ import annotations

import random

import httpx
from bb_paxdata.infrastructure.tasks.celery_app import app as celery_app
from bb_paxdata.infrastructure.webhooks.signature import generate_webhook_signature
from celery import Task
from celery.utils.log import get_task_logger

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
) -> dict:
    """
    Webhook isteğini gönderir. Başarısızlıkta exponential backoff ile tekrar dener.
    MaxRetry aşımında event dead_letter_events tablosuna taşınır.
    """
    signature_header, _ = generate_webhook_signature(payload, secret)

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                endpoint_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Paxdata-Signature": signature_header,
                    "X-Paxdata-Event-Id": event_id,
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
            return {"status": "permanent_failure", "http_status": response.status_code}

        # 5xx: geçici hata, retry
        raise httpx.HTTPStatusError(
            f"Server error {response.status_code}",
            request=response.request,
            response=response,
        )

    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
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
        raise self.retry(exc=exc, countdown=countdown)


def _mark_event_processed(event_id: str) -> None:
    """OutboxEvent'i processed=True olarak günceller."""
    from datetime import datetime, timezone

    from bb_paxdata.infrastructure.db.models import OutboxEventORM
    from bb_paxdata.infrastructure.db.session import get_db_session

    with get_db_session() as session:
        event = session.get(OutboxEventORM, event_id)
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
        original = session.get(OutboxEventORM, event_id)
        if original:
            dead = DeadLetterEventORM(
                original_event_id=event_id,
                event_type=original.event_type,
                payload=payload,
                failure_reason=reason,
            )
            session.add(dead)
            original.processed = True  # outbox'tan temizle
            session.commit()
