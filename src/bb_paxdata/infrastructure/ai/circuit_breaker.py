"""Circuit breaker for AI service calls with fallback mechanism.

Provides protection for AI service calls with configurable thresholds,
half-open state recovery, and fallback responses.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Circuit open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5  # Consecutive failures to open circuit
    success_threshold: int = 2  # Successes in half-open to close circuit
    open_timeout_seconds: int = 60  # Time before attempting recovery
    timeout_seconds: int = 120  # Request timeout
    fallback_enabled: bool = True  # Whether to use fallback responses


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: float | None
    last_success_time: float | None
    opened_at: float | None


class AICircuitBreaker:
    """Circuit breaker for AI service calls with in-memory state.

    For distributed state, use the Redis-based circuit breaker in
    infrastructure/webhooks/circuit_breaker.py instead.
    """

    def __init__(
        self,
        service_name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self._service_name = service_name
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._last_success_time: float | None = None
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    async def get_state(self) -> CircuitState:
        """Get current circuit state."""
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if (
                    self._opened_at
                    and (time.time() - self._opened_at)
                    > self._config.open_timeout_seconds
                ):
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info(
                        "circuit_breaker.half_open",
                        service=self._service_name,
                        open_duration_seconds=time.time() - (self._opened_at or 0),
                    )
        return self._state

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._last_success_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._opened_at = None
                    logger.info(
                        "circuit_breaker.closed",
                        service=self._service_name,
                        success_count=self._success_count,
                    )
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._last_failure_time = time.time()
            self._failure_count += 1

            if self._state == CircuitState.CLOSED:
                if self._failure_count >= self._config.failure_threshold:
                    await self._open_circuit()
            elif self._state == CircuitState.HALF_OPEN:
                await self._open_circuit()

    async def _open_circuit(self) -> None:
        """Open the circuit."""
        self._state = CircuitState.OPEN
        self._opened_at = time.time()
        logger.warning(
            "circuit_breaker.opened",
            service=self._service_name,
            failure_count=self._failure_count,
        )

    async def is_allowed(self) -> bool:
        """Check if a request is allowed through the circuit."""
        state = await self.get_state()
        return state != CircuitState.OPEN

    def get_stats(self) -> CircuitBreakerStats:
        """Get current circuit breaker statistics."""
        return CircuitBreakerStats(
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            last_failure_time=self._last_failure_time,
            last_success_time=self._last_success_time,
            opened_at=self._opened_at,
        )


# Global circuit breaker instances for AI services
_circuit_breakers: dict[str, AICircuitBreaker] = {}
_circuit_lock = asyncio.Lock()


def get_circuit_breaker(
    service_name: str,
    config: CircuitBreakerConfig | None = None,
) -> AICircuitBreaker:
    """Get or create a circuit breaker for a service."""
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = AICircuitBreaker(service_name, config)
    return _circuit_breakers[service_name]


async def with_circuit_breaker(
    service_name: str,
    func: Callable,
    *args: Any,
    fallback_response: Any = None,
    config: CircuitBreakerConfig | None = None,
    **kwargs: Any,
) -> Any:
    """Execute a function with circuit breaker protection.

    Args:
        service_name: Name of the AI service (e.g., "anthropic", "gemini")
        func: The async function to execute
        *args: Arguments to pass to the function
        fallback_response: Response to return when circuit is open
        config: Circuit breaker configuration
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The function result or fallback response if circuit is open

    Raises:
        Exception: If the function fails and circuit is not open
    """
    cb = get_circuit_breaker(service_name, config)

    # Check if request is allowed
    if not await cb.is_allowed():
        logger.warning(
            "circuit_breaker.rejected",
            service=service_name,
            state=cb.get_state().value,
        )
        if fallback_response is not None:
            return fallback_response
        raise Exception(f"Circuit breaker open for {service_name}")

    # Execute with timeout
    try:
        cfg = config or CircuitBreakerConfig()
        result = await asyncio.wait_for(
            func(*args, **kwargs),
            timeout=cfg.timeout_seconds,
        )
        await cb.record_success()
        return result
    except TimeoutError:
        await cb.record_failure()
        logger.error(
            "circuit_breaker.timeout",
            service=service_name,
            timeout=cfg.timeout_seconds,
        )
        if fallback_response is not None:
            return fallback_response
        raise
    except Exception as e:
        await cb.record_failure()
        logger.error(
            "circuit_breaker.failure",
            service=service_name,
            error=str(e),
        )
        if fallback_response is not None:
            return fallback_response
        raise


def get_all_circuit_breaker_stats() -> dict[str, dict[str, Any]]:
    """Get statistics for all circuit breakers."""
    return {
        name: {
            "state": cb.get_state().value,
            "failure_count": cb.get_stats().failure_count,
            "success_count": cb.get_stats().success_count,
            "last_failure_time": cb.get_stats().last_failure_time,
            "last_success_time": cb.get_stats().last_success_time,
            "opened_at": cb.get_stats().opened_at,
        }
        for name, cb in _circuit_breakers.items()
    }
