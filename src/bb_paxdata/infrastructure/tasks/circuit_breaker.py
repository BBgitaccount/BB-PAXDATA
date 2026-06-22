"""Circuit breaker for LLM service calls in Celery tasks.

Prevents infinite retries when LLM service is down (BUG-SYS-007 fix).
"""

import structlog
from circuitbreaker import CircuitBreaker, CircuitBreakerError

logger = structlog.get_logger(__name__)


# Circuit breaker for LLM service calls
# Opens after 5 consecutive failures, stays open for 60 seconds
llm_circuit = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=(ConnectionError, TimeoutError, Exception),
)


def llm_service_circuit_breaker(func):
    """Decorator to apply circuit breaker to LLM service calls.

    Args:
        func: The function to protect with circuit breaker

    Returns:
        Wrapped function with circuit breaker protection

    Circuit breaker behavior:
    - Opens after 5 consecutive failures
    - Stays open for 60 seconds before attempting recovery
    - Closes when a call succeeds during recovery
    """
    protected_func = llm_circuit(func)

    def wrapper(*args, **kwargs):
        try:
            result = protected_func(*args, **kwargs)
            logger.info("circuitbreaker.success", function=func.__name__)
            return result
        except CircuitBreakerError as e:
            logger.error(
                "circuitbreaker.open",
                function=func.__name__,
                error=str(e),
            )
            raise
        except Exception as e:
            logger.warning(
                "circuitbreaker.failure",
                function=func.__name__,
                error=str(e),
            )
            raise

    return wrapper


def get_circuit_breaker_state() -> dict[str, any]:
    """Get current circuit breaker state for monitoring.

    Returns:
        Dictionary with circuit breaker state information
    """
    return {
        "circuit_breaker_enabled": True,
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "current_state": llm_circuit.current_state,
        "failure_count": llm_circuit.failure_count,
        "last_failure": llm_circuit.last_failure,
    }
