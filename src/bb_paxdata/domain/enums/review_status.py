from __future__ import annotations

from enum import StrEnum


class ReviewStatus(StrEnum):
    """İnsan inceleme talebi durumu."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
