from __future__ import annotations

from bb_paxdata.application.services.cross_anomaly_service import (
    ContradictionResult,
    CrossAnomalyService,
)
from bb_paxdata.domain.enums.anomaly_type import AnomalyType
from bb_paxdata.domain.enums.negation_type import NegationType
from bb_paxdata.domain.models.negation_cue import NegationCue
from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.models.sentence import Sentence


class CrossAnomalyServiceImpl(CrossAnomalyService):
    """Tsytsarau (2017) contradiction measure implementasyonu.

    Reference:
        - Tsytsarau, M. et al. (2017). Identifying Sentiment-based
          Contradictions.
          C = (n·M₂ − M₁²) / ((ϑ·n² + M₁²)·W)
    """

    async def detect_sentiment_risk_divergence(
        self,
        segment: Segment,
        polarity_values: list[float],
        theta: float = 0.1,
        window: float | None = None,
        threshold: float = 0.5,
    ) -> ContradictionResult:
        """Contradiction measure C hesaplar.

        Args:
            segment: Analiz edilen metin segmenti.
            polarity_values: Her cümlenin polarity skoru (örn. VADER compound).
                             Değer aralığı: [-1.0, 1.0]
            theta: Hassasiyet parametresi (ϑ). Varsayılan 0.1.
            window: Pencere boyutu (W). None ise n kullanılır.
            threshold: Anomali eşiği. C > threshold ise anomali.

        Returns:
            ContradictionResult: Hesaplanan C değeri ve metadata.

        Raises:
            ValueError: polarity_values boş ise.
        """
        if not polarity_values:
            raise ValueError("polarity_values boş olamaz")

        n = len(polarity_values)

        # Moment hesaplamaları
        m1 = sum(polarity_values) / n  # Birinci moment (ortalama)
        m2 = sum(p * p for p in polarity_values) / n  # İkinci moment

        # Pencere boyutu
        w = window if window is not None else float(n)

        # Numerator ve denominator
        # C = (n·M₂ − M₁²) / ((ϑ·n² + M₁²)·W)
        numerator = (n * m2) - (m1 * m1)
        denominator = ((theta * n * n) + (m1 * m1)) * w

        # C değeri (0'a bölme koruması)
        if denominator == 0:
            c = 0.0
        else:
            c = numerator / denominator

        # Faz 2: Negasyon filtrelemesi
        adjustment = self._compute_negation_adjustment(segment.sentences)
        adjusted_score = max(0.0, c - adjustment)
        is_anomaly = adjusted_score > threshold

        return ContradictionResult(
            score=round(adjusted_score, 6),
            threshold=threshold,
            is_anomaly=is_anomaly,
            anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
            n_sentences=n,
            m1=round(m1, 6),
            m2=round(m2, 6),
            theta=theta,
            window=w,
        )

    def _compute_negation_adjustment(self, sentences: list[Sentence]) -> float:
        """Negasyon kaynaklı false positive'leri hesapla ve düzeltme katsayısı üret."""
        if not sentences:
            return 0.0

        total_adjustment = 0.0
        for sentence in sentences:
            for cue in sentence.negation_cues:
                total_adjustment += self._evaluate_cue_false_positive_risk(
                    cue, sentence
                )

        # Normalize: cümle başına ortalama düzeltme
        return min(1.0, total_adjustment / len(sentences))

    def _evaluate_cue_false_positive_risk(
        self, cue: NegationCue, sentence: Sentence
    ) -> float:
        """Tek bir negasyon cue'yu için false positive risk skoru."""
        # SEMANTIC cue'lar zaten negatif sentiment'tir — contradiction değil
        if cue.negation_type == NegationType.SEMANTIC and cue.confidence > 0.8:
            return 0.35  # Yüksek düzeltme

        # SURFACE cue + kısa scope: VADER zaten negasyon heuristic'i uygular
        if cue.negation_type == NegationType.SURFACE and not cue.has_scope:
            return 0.25

        # SYNTACTIC cue + scope tespiti
        if cue.negation_type == NegationType.SYNTACTIC and cue.has_scope:
            return 0.20

        # SCOPE_WIDE: Geniş kapsamda contradiction daha muhtemeldir, düzeltme az
        if cue.negation_type == NegationType.SCOPE_WIDE:
            return 0.10

        return 0.0

    async def detect_power_asymmetry_anomaly(
        self,
        asymmetry_score: float,
        sentiment_delta: float,
        threshold_asymmetry: float = 0.5,
        threshold_delta: float = -0.3,
    ) -> bool:
        """Güç asimetrisi ve sentiment farkı üzerinden anomali tespiti.

        asymmetry_score > 0.5 + sentiment_delta < -0.3 -> POWER_ASYMMETRY_ANOMALY
        """
        return (
            asymmetry_score > threshold_asymmetry and sentiment_delta < threshold_delta
        )

    async def detect_cheap_talk_anomaly(
        self,
        power_weighted_score: float,
        signal_credibility: float,
        threshold_power: float = 0.1,
        threshold_credibility: float = 0.4,
    ) -> bool:
        """Cheap talk anomalisi tespiti.

        power_weighted_score > threshold + signal_credibility < 0.4 -> CHEAP_TALK_ANOMALY
        """
        return (
            power_weighted_score > threshold_power
            and signal_credibility < threshold_credibility
        )
