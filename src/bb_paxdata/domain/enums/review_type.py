from __future__ import annotations

from enum import StrEnum


class ReviewType(StrEnum):
    """İnsan doğrulama inceleme türleri.

    Reference:
        - Grimmer & Stewart (2013) - Principle 4: Exploratory vs. Confirmatory.
    """

    EXPLORATORY = "exploratory"
    """Keşfedici analiz; yeni kalıplar veya anomalileri belirlemek için."""

    CONFIRMATORY = "confirmatory"
    """Doğrulayıcı analiz; AI çıktılarının doğruluğunu onaylamak için."""

    ESCALATION = "escalation"
    """Üst birime iletme; AI modellerinin düşük güvenle ürettiği veya çelişkili durumlar."""
