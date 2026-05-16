from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from ..utils.statistics import StatisticalUtils
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class EntityFlipConfig:
    """Entity Flip kuralı için konfigürasyon."""

    window_size: int = 3
    flip_threshold: float = 1.2  # Örn: +0.8'den -0.4'e geçiş
    entity_types: tuple = ("GPE", "PERSON")


class EntityFlipRule(BaseAnomalyRule):
    """
    ID: RULE_ENTITY_FLIP
    Mantık: Aynı entity (GPE veya Person) 3 cümlelik kayan pencerede
            taban tabana zıt duygu skorları alıyorsa anomali.
    """

    def __init__(self, config: EntityFlipConfig | None = None):
        self._config = config or EntityFlipConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_ENTITY_FLIP"

    @property
    def rule_name(self) -> str:
        return "Entity Flip (Varlık Zıtlığı)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.HIGH

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        max_confidence = 0.0
        anomalous_segments = []
        flip_metadata = {}

        for segment in analysis.transcript.segments:
            sentences = list(segment.sentences)
            if len(sentences) < self._config.window_size:
                continue

            # Her cümle için NER sonuçlarını cache'le
            sentence_entities = []
            for sent in sentences:
                # Text bazlı cache anahtarı kullanıyoruz
                entities = context.get_cached(
                    f"ner_{hash(sent.text)}",
                    lambda s=sent: context.ner_service.extract_entities(s.text),
                )
                filtered = [
                    e for e in entities if e.get("type") in self._config.entity_types
                ]
                sentence_entities.append(filtered)

            # İndisler üzerinden kayan pencere
            windows = StatisticalUtils.sliding_window(
                list(range(len(sentences))), self._config.window_size
            )

            for window_indices in windows:
                # Pencere içindeki varlıkların duygu skorlarını topla
                window_entity_map: dict[str, list[tuple]] = {}

                for idx in window_indices:
                    sent = sentences[idx]
                    entities = sentence_entities[idx]
                    for ent in entities:
                        ent_text = ent.get("text", "").lower().strip()
                        if ent_text:
                            if ent_text not in window_entity_map:
                                window_entity_map[ent_text] = []
                            window_entity_map[ent_text].append(
                                (idx, sent.sentiment_score, ent.get("type"))
                            )

                for ent_text, occurrences in window_entity_map.items():
                    if len(occurrences) < 2:
                        continue

                    scores = [occ[1] for occ in occurrences]
                    max_score = max(scores)
                    min_score = min(scores)
                    flip_size = max_score - min_score

                    if flip_size >= self._config.flip_threshold:
                        ent_type = occurrences[0][2]
                        type_weight = 1.0 if ent_type == "GPE" else 0.9
                        # Flip büyüklüğünü normalleştir (max flip = 2.0)
                        confidence = min(1.0, (flip_size / 2.0) * type_weight)

                        if confidence > max_confidence:
                            max_confidence = confidence
                            anomalous_segments = [
                                SegmentRef(
                                    segment_id=segment.segment_id,
                                    start_time=segment.start_time,
                                    end_time=segment.end_time,
                                )
                            ]
                            flip_metadata = {
                                "entity": ent_text,
                                "entity_type": ent_type,
                                "flip_size": flip_size,
                                "scores": scores,
                                "window_indices": window_indices,
                            }

        if not anomalous_segments:
            return None

        return AnomalyResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            confidence_score=max_confidence,
            description=f"Varlık '{flip_metadata.get('entity')}' için zıt duygu skorları tespit edildi ({flip_metadata.get('flip_size', 0):.2f}).",
            affected_segments=anomalous_segments,
            metadata=flip_metadata,
        )
