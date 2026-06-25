# src/bb_paxdata/infrastructure/webhooks/circuit_breaker.py
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

from redis.asyncio import Redis


class CircuitState(StrEnum):
    CLOSED = "CLOSED"  # Normal, istekler geçiyor
    OPEN = "OPEN"  # Devre açık, istekler fast-fail
    HALF_OPEN = "HALF_OPEN"  # Test isteği gönderiliyor


@dataclass(frozen=True)
class CircuitBreakerConfig:
    failure_threshold: int = 5  # Kaç ardışık hata → OPEN
    success_threshold: int = 2  # HALF_OPEN'da kaç başarı → CLOSED
    open_timeout_seconds: int = 60  # OPEN → HALF_OPEN için bekleme süresi


class CircuitBreaker:
    """
    Redis-tabanlı circuit breaker. State, tüm worker'lar arasında paylaşılır.
    Key format: cb:{endpoint_id}:{field}
    """

    def __init__(
        self, redis: Redis, endpoint_id: str, config: CircuitBreakerConfig | None = None
    ) -> None:
        self._redis = redis
        self._prefix = f"cb:{endpoint_id}"
        self._cfg = config or CircuitBreakerConfig()

    async def get_state(self) -> CircuitState:
        state_raw = await self._redis.get(f"{self._prefix}:state")
        if state_raw is None:
            return CircuitState.CLOSED
        return CircuitState(state_raw.decode())

    async def record_success(self) -> None:
        state = await self.get_state()
        if state == CircuitState.HALF_OPEN:
            count = await self._redis.incr(f"{self._prefix}:success_count")
            if count >= self._cfg.success_threshold:
                await self._reset()

    async def record_failure(self) -> None:
        state = await self.get_state()
        if state == CircuitState.OPEN:
            return  # Zaten açık, kayıt gereksiz

        count = await self._redis.incr(f"{self._prefix}:failure_count")
        if count >= self._cfg.failure_threshold:
            await self._open()

    async def is_allowed(self) -> bool:
        state = await self.get_state()
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            # Timeout geçti mi? Geçtiyse HALF_OPEN'a geç
            opened_at = await self._redis.get(f"{self._prefix}:opened_at")
            if (
                opened_at
                and (time.time() - float(opened_at)) > self._cfg.open_timeout_seconds
            ):
                await self._half_open()
                return True  # Test isteğine izin ver
            return False
        # HALF_OPEN → tek test isteğine izin ver
        return True

    async def _open(self) -> None:
        pipe = self._redis.pipeline()
        pipe.set(f"{self._prefix}:state", CircuitState.OPEN.value)
        pipe.set(f"{self._prefix}:opened_at", str(time.time()))
        pipe.delete(f"{self._prefix}:success_count")
        await pipe.execute()

    async def _half_open(self) -> None:
        await self._redis.set(f"{self._prefix}:state", CircuitState.HALF_OPEN.value)

    async def _reset(self) -> None:
        pipe = self._redis.pipeline()
        pipe.delete(f"{self._prefix}:state")
        pipe.delete(f"{self._prefix}:failure_count")
        pipe.delete(f"{self._prefix}:success_count")
        pipe.delete(f"{self._prefix}:opened_at")
        await pipe.execute()
