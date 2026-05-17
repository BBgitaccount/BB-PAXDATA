from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from ..utils.confidence import ConfidenceCalculator
from ..utils.statistics import StatisticalUtils
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class SpeakerInconsistencyConfig:
    """Konuşmacı tutarsızlığı kuralı konfigürasyonu."""

    z_threshold: float = 2.5
    min_history: int = 3


class SpeakerInconsistencyRule(BaseAnomalyRule):
    """
    ID: RULE_SPEAKER_INCONSISTENCY
    Mantık: Konuşmacının SBI risk skorlarının geçmiş verilerden anlamlı derecede sapması.
    """

    def __init__(self, config: SpeakerInconsistencyConfig | None = None):
        self._config = config or SpeakerInconsistencyConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_SPEAKER_INCONSISTENCY"

    @property
    def rule_name(self) -> str:
        return "Speaker Inconsistency (Konuşmacı Tutarsızlığı)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.MEDIUM

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        max_confidence = 0.0
        anomalous_segments = []
        best_metadata = {}

        for segment in analysis.transcript.segments:
            speaker_id = segment.speaker_id
            if not speaker_id:
                continue

            current_sbi = analysis.metadata.get("sbi_score")
            if current_sbi is None:
                continue

            try:
                # Geçmiş verileri servisten çek
                history = context.speaker_service.get_historical_sbi(
                    speaker_id, analysis.metadata.get("context_id", "default")
                )
            except Exception:
                continue

            if len(history) < self._config.min_history:
                continue

            mean = sum(history) / len(history)
            std = StatisticalUtils.compute_std(history)

            if std == 0:
                if current_sbi != mean:
                    confidence = 0.95
                else:
                    continue
            else:
                z = abs(current_sbi - mean) / std
                if z < self._config.z_threshold:
                    continue
                confidence = ConfidenceCalculator.from_z_score(z, max_z=5.0)

                # Geçmiş veri sayısına göre güveni ayarla
                if len(history) < 5:
                    confidence *= 0.7
                elif len(history) >= 10:
                    confidence = min(1.0, confidence * 1.1)

            if confidence > max_confidence:
                max_confidence = confidence
                anomalous_segments = [
                    SegmentRef(
                        segment_id=segment.segment_id,
                        start_time=segment.start_time,
                        end_time=segment.end_time,
                    )
                ]
                best_metadata = {
                    "speaker_id": speaker_id,
                    "current_sbi": current_sbi,
                    "historical_mean": mean,
                    "historical_std": std,
                    "history_count": len(history),
                    "z_score": z if std != 0 else float("inf"),
                }

        if not anomalous_segments:
            return None

        return AnomalyResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            confidence_score=max_confidence,
            description=f"Konuşmacı {best_metadata.get('speaker_id')} için SBI skoru tutarsızlığı tespit edildi.",
            affected_segments=anomalous_segments,
            metadata=best_metadata,
        )
