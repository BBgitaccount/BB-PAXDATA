from __future__ import annotations

from enum import StrEnum


class Priority(StrEnum):
    """İnceleme talebi öncelik seviyeleri."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
