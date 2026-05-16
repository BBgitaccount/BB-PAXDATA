from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class OverlappingClaimConfig:
    """Overlapping claim kuralı konfigürasyonu."""

    mutually_exclusive_verbs: set[tuple[str, str]] = None

    def __post_init__(self):
        if self.mutually_exclusive_verbs is None:
            object.__setattr__(
                self,
                "mutually_exclusive_verbs",
                {
                    ("cause", "prevent"),
                    ("decrease", "increase"),
                    ("start", "stop"),
                    ("oppose", "support"),
                    ("accept", "reject"),
                    ("engelle", "neden ol"),
                    ("arttır", "azalt"),
                    ("başlat", "durdur"),
                },
            )


class OverlappingClaimRule(BaseAnomalyRule):
    """
    ID: RULE_OVERLAPPING_CLAIM
    Mantık: Birden fazla konuşmacının aynı olaya birbirini dışlayan nedensellikler ataması.
    """

    def __init__(self, config: OverlappingClaimConfig | None = None):
        self._config = config or OverlappingClaimConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_OVERLAPPING_CLAIM"

    @property
    def rule_name(self) -> str:
        return "Overlapping Claim (Örtüşen/Çatışan İddia)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.HIGH

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        # Konuşmacı bazlı iddiaları topla
        speaker_claims: dict[str, list[dict]] = {}

        for segment in analysis.transcript.segments:
            speaker = segment.speaker_id or "unknown"
            if speaker not in speaker_claims:
                speaker_claims[speaker] = []

            for sentence in segment.sentences:
                try:
                    # SVOExtractor servisini kullan
                    svos = context.svo_extractor.extract_svo_triples(sentence.text)
                except Exception:
                    continue

                for svo in svos:
                    speaker_claims[speaker].append(
                        {
                            "subject": svo.get("subject", "").lower(),
                            "verb": svo.get("verb", "").lower(),
                            "object": svo.get("object", "").lower(),
                            "causality": svo.get("causality_type", "unknown"),
                            "segment_id": segment.segment_id,
                        }
                    )

        if len(speaker_claims) < 2:
            return None

        conflict_count = 0
        conflicting_pairs = []
        anomalous_segments_ids = set()

        speakers = list(speaker_claims.keys())
        for i, spk1 in enumerate(speakers):
            for spk2 in speakers[i + 1 :]:
                for claim1 in speaker_claims[spk1]:
                    for claim2 in speaker_claims[spk2]:
                        # Aynı özne ve nesne, ancak çelişen fiil kontrolü
                        if (
                            claim1["subject"] == claim2["subject"]
                            and claim1["object"] == claim2["object"]
                            and claim1["subject"]
                            and claim1["object"]
                        ):

                            verb_pair = tuple(sorted([claim1["verb"], claim2["verb"]]))
                            if verb_pair in self._config.mutually_exclusive_verbs:
                                conflict_count += 1
                                conflicting_pairs.append(
                                    {
                                        "speaker1": spk1,
                                        "speaker2": spk2,
                                        "claim1": claim1,
                                        "claim2": claim2,
                                    }
                                )
                                anomalous_segments_ids.add(claim1["segment_id"])
                                anomalous_segments_ids.add(claim2["segment_id"])

        if conflict_count == 0:
            return None

        # Çatışma sayısına göre confidence belirle
        if conflict_count == 2:
            confidence = 0.7
        elif conflict_count >= 3:
            confidence = 0.9
        else:
            confidence = 0.6

        # Etkilenen segmentleri modellerden geri bul
        anomalous_segments = []
        for segment in analysis.transcript.segments:
            if segment.segment_id in anomalous_segments_ids:
                anomalous_segments.append(
                    SegmentRef(
                        segment_id=segment.segment_id,
                        start_time=segment.start_time,
                        end_time=segment.end_time,
                    )
                )

        return AnomalyResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            confidence_score=confidence,
            description=f"Konuşmacılar arasında {conflict_count} adet çelişkili nedensellik iddiası tespit edildi.",
            affected_segments=anomalous_segments,
            metadata={
                "conflict_count": conflict_count,
                "speaker_count": len(speaker_claims),
                "conflicting_pairs": conflicting_pairs[:5],
            },
        )
