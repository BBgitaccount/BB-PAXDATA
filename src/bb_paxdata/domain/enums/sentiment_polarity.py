from __future__ import annotations

from enum import StrEnum


class SentimentPolarity(StrEnum):
    """Duygu polaritesi sınıflandırması."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"  # Modeller arası çelişki durumunda
