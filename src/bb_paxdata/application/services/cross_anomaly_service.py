from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bb_paxdata.domain.enums.anomaly_type import AnomalyType
from bb_paxdata.domain.models.segment import Segment


@dataclass(frozen=True)
class ContradictionResult:
    """Tsytsarau (2017) contradiction measure sonucu.

    Attributes:
        score: C değeri (0.0 = çelişki yok, 1.0+ = yüksek çelişki)
        threshold: Tetikleme eşiği (varsayılan 0.5)
        is_anomaly: C > threshold mu?
        anomaly_type: SENTIMENT_RISK_DIVERGENCE
        n_sentences: Cümle sayısı
        m1: Birinci moment (ortalama polarity)
        m2: İkinci moment (polarity kareler ortalaması)
        theta: Kullanılan hassasiyet parametresi
        window: Kullanılan pencere boyutu
    """

    score: float
    threshold: float
    is_anomaly: bool
    anomaly_type: AnomalyType
    n_sentences: int
    m1: float
    m2: float
    theta: float
    window: float


class CrossAnomalyService(Protocol):
    """Duygu-risk çelişkisi ve diğer anomali tespit servisi.

    Faz 1'de Tsytsarau (2017) contradiction measure implemente edilir.
    Faz 3'te Zagare (2004) risk çarpanları ile entegre edilecektir.
    """

    async def detect_sentiment_risk_divergence(
        self,
        segment: Segment,
        polarity_values: list[float],
        theta: float = 0.1,
        window: float | None = None,
        threshold: float = 0.5,
    ) -> ContradictionResult: ...

    async def detect_power_asymmetry_anomaly(
        self,
        asymmetry_score: float,
        sentiment_delta: float,
        threshold_asymmetry: float = 0.5,
        threshold_delta: float = -0.3,
    ) -> bool: ...

    async def detect_cheap_talk_anomaly(
        self,
        power_weighted_score: float,
        signal_credibility: float,
        threshold_power: float = 0.1,
        threshold_credibility: float = 0.4,
    ) -> bool: ...
