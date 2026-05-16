from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class TemporalGapConfig:
    """Zaman boşluğu kuralı konfigürasyonu."""

    min_gap_seconds: float = 30.0
    anaphora_lookahead: int = 3


class TemporalGapRule(BaseAnomalyRule):
    """
    ID: RULE_TEMPORAL_GAP
    Mantık: Uzun sessizlik sonrası önceki konuya (çözülemeyen anafora) referans verme.
    """

    def __init__(self, config: TemporalGapConfig | None = None):
        self._config = config or TemporalGapConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_TEMPORAL_GAP"

    @property
    def rule_name(self) -> str:
        return "Temporal Gap (Zaman Boşluğu ve Anafora)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.MEDIUM

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        gaps = analysis.transcript.silence_gaps
        if not gaps:
            return None

        segments = list(analysis.transcript.segments)
        max_confidence = 0.0
        anomalous_segments = []
        best_metadata = {}

        for gap_start, gap_end in gaps:
            gap_duration = gap_end - gap_start
            if gap_duration < self._config.min_gap_seconds:
                continue

            # Boşluktan sonraki segmentleri bul
            post_segments = [s for s in segments if s.start_time >= gap_end]
            if not post_segments:
                continue

            # Boşluk sonrası ilk birkaç segmentte çözülemeyen anafora ara
            unresolved_count = 0
            for segment in post_segments[: self._config.anaphora_lookahead]:
                for sentence in segment.sentences:
                    try:
                        deps = context.dependency_service.extract_dependencies(
                            sentence.text
                        )
                    except Exception:
                        continue

                    for dep in deps:
                        # Pronominal referansları kontrol et
                        if dep.get("rel") in ("anaphora", "ref"):
                            ref_target = dep.get("dep", "").lower()
                            if ref_target in (
                                "it",
                                "they",
                                "this",
                                "that",
                                "he",
                                "she",
                            ):
                                # Basitleştirilmiş: Eğer bu referans mevcut segmentte çözülemiyorsa
                                unresolved_count += 1

            if unresolved_count == 0:
                continue

            # Confidence hesaplama
            gap_factor = min(1.0, (gap_duration - self._config.min_gap_seconds) / 90.0)
            anaphora_bonus = min(0.2, unresolved_count * 0.1)
            confidence = 0.5 + (gap_factor * 0.3) + anaphora_bonus
            confidence = min(0.95, confidence)

            if confidence > max_confidence:
                max_confidence = confidence
                anomalous_segments = [
                    SegmentRef(
                        segment_id=s.segment_id,
                        start_time=s.start_time,
                        end_time=s.end_time,
                    )
                    for s in post_segments[: self._config.anaphora_lookahead]
                ]
                best_metadata = {
                    "gap_duration": gap_duration,
                    "gap_start": gap_start,
                    "gap_end": gap_end,
                    "unresolved_anaphora": unresolved_count,
                }

        if not anomalous_segments:
            return None

        return AnomalyResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            confidence_score=max_confidence,
            description=f"{best_metadata.get('gap_duration', 0):.1f}sn sessizlik sonrası çözülemeyen anafora tespiti.",
            affected_segments=anomalous_segments,
            metadata=best_metadata,
        )
