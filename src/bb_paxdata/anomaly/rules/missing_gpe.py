from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class MissingGPEConfig:
    """Missing GPE kuralı konfigürasyonu."""

    policy_verbs: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.policy_verbs is None:
            object.__setattr__(
                self,
                "policy_verbs",
                {
                    "invade": 1.0,
                    "işgal": 1.0,
                    "sanction": 0.9,
                    "yaptırım": 0.9,
                    "attack": 0.8,
                    "saldır": 0.8,
                    "annex": 0.85,
                    "ilhak": 0.85,
                    "occupy": 0.9,
                    "işgal et": 0.9,
                    "bomb": 0.8,
                    "bombala": 0.8,
                    "blockade": 0.85,
                    "abluka": 0.85,
                },
            )


class MissingGPERule(BaseAnomalyRule):
    """
    ID: RULE_MISSING_GPE
    Mantık: Politika fiili kullanılmasına rağmen cümlede herhangi bir GPE argümanı bulunmaması.
    """

    def __init__(self, config: MissingGPEConfig | None = None):
        self._config = config or MissingGPEConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_MISSING_GPE"

    @property
    def rule_name(self) -> str:
        return "Missing GPE (Eksik Geopolitik Varlık)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.HIGH

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        max_confidence = 0.0
        anomalous_segments = []
        best_metadata = {}

        for segment in analysis.transcript.segments:
            for sentence in segment.sentences:
                try:
                    # Dependency ve NER servislerini kullan
                    deps = context.dependency_service.extract_dependencies(
                        sentence.text
                    )
                    entities = context.ner_service.extract_entities(sentence.text)
                except Exception:
                    continue

                gpe_entities = [e for e in entities if e.get("type") == "GPE"]

                # Politika fiillerini ve nesnelerini bul
                for dep in deps:
                    head = dep.get("head", "").lower()
                    rel = dep.get("rel", "")
                    dep_word = dep.get("dep", "").lower()

                    policy_verbs = self._config.policy_verbs or {}
                    verb_weight = policy_verbs.get(head)
                    if not verb_weight:
                        continue

                    # Nesne (object) ilişkisi kontrolü
                    if rel in ("dobj", "obj"):
                        if not gpe_entities:
                            # Cümlede hiç GPE yok
                            confidence = verb_weight * 0.95
                        else:
                            # Nesne var ama GPE değil
                            obj_is_gpe = any(
                                e.get("text", "").lower() == dep_word
                                for e in gpe_entities
                            )
                            if not obj_is_gpe:
                                confidence = verb_weight * 0.6
                            else:
                                continue

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
                                "verb": head,
                                "verb_weight": verb_weight,
                                "relation": rel,
                                "gpe_count": len(gpe_entities),
                            }

        if not anomalous_segments:
            return None

        return AnomalyResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            confidence_score=max_confidence,
            description=f"Politika fiili '{best_metadata.get('verb')}' için GPE argümanı eksikliği tespit edildi.",
            affected_segments=anomalous_segments,
            metadata=best_metadata,
        )
