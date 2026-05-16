from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from ..utils.confidence import ConfidenceCalculator
from ..utils.statistics import StatisticalUtils
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class ToneDriftConfig:
    """Kurala özgü konfigürasyon."""

    sigma_multiplier: float = 2.0
    min_sentences: int = 3


class ToneDriftRule(BaseAnomalyRule):
    """
    ID: RULE_TONE_DRIFT
    Mantık: Tek segment içinde ardışık cümlelerin sentiment skorlarının varyansı
           popülasyonun 2 standart sapması (2σ) üzerine çıkarsa anomali.
    """

    def __init__(self, config: ToneDriftConfig | None = None):
        self._config = config or ToneDriftConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_TONE_DRIFT"

    @property
    def rule_name(self) -> str:
        return "Tone Drift (Ton Kayması)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.MEDIUM

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        max_confidence = 0.0
        anomalous_segments = []

        for segment in analysis.transcript.segments:
            sentences = segment.sentences
            if len(sentences) < self._config.min_sentences:
                continue

            scores = [s.sentiment_score for s in sentences]
            std = StatisticalUtils.compute_std(scores)

            if std == 0:
                continue

            mean = sum(scores) / len(scores)
            threshold = self._config.sigma_multiplier * std

            # Her bir cümlenin ortalamadan sapmasını kontrol et
            max_deviation = max(abs(s - mean) for s in scores)

            if max_deviation > threshold:
                z = max_deviation / std
                confidence = ConfidenceCalculator.from_z_score(z, max_z=4.0)

                if confidence > max_confidence:
                    max_confidence = confidence
                    anomalous_segments = [
                        SegmentRef(
                            segment_id=segment.segment_id,
                            start_time=segment.start_time,
                            end_time=segment.end_time,
                        )
                    ]

        if not anomalous_segments:
            return None

        return AnomalyResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            confidence_score=max_confidence,
            description=f"Sentiment sapması {self._config.sigma_multiplier}σ eşiğini aştı.",
            affected_segments=anomalous_segments,
            metadata={"sigma_multiplier": self._config.sigma_multiplier},
        )
