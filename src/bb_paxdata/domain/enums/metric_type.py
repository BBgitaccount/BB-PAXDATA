from __future__ import annotations

from enum import StrEnum


class MetricType(StrEnum):
    """Analiz metrik türleri."""

    SBI = "sbi"
    """Strategic Balance Index"""

    DKI = "dki"
    """Diplomatic Knowledge Index"""

    RISK = "risk"
    """Overall Risk Score"""

    SENTIMENT = "sentiment"
    """Sentiment Analysis Score"""
