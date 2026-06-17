# src/bb_paxdata/application/domain/utils/context.py
from __future__ import annotations

import contextvars

# ContextVar to hold the correlation ID for the current request context/task
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> str | None:
    """Retrieve the correlation ID of the current request/context."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str | None) -> None:
    """Set the correlation ID for the current request/context."""
    correlation_id_var.set(correlation_id)
