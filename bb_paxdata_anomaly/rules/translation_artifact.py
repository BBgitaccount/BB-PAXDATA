from collections import Counter
from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from ..utils.confidence import ConfidenceCalculator
from ..utils.statistics import StatisticalUtils
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class TranslationArtifactConfig:
    """Translation artifact kuralı konfigürasyonu."""

    min_tokens: int = 10
    ngram_weights: dict[int, float] = None
    reference_profile: dict[str, float] = None

    def __post_init__(self):
        if self.ngram_weights is None:
            object.__setattr__(self, "ngram_weights", {1: 0.2, 2: 0.3, 3: 0.5})


class TranslationArtifactRule(BaseAnomalyRule):
    """
    ID: RULE_TRANSLATION_ARTIFACT
    Mantık: POS n-gram dağılımında doğal dilden sapan istatistiksel kaymalar (MT tespiti).
    """

    def __init__(self, config: TranslationArtifactConfig | None = None):
        self._config = config or TranslationArtifactConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_TRANSLATION_ARTIFACT"

    @property
    def rule_name(self) -> str:
        return "Translation Artifact (Çeviri Yapaylığı)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.LOW

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        # Referans profilini al
        ref_profile = self._config.reference_profile
        if not ref_profile:
            ref_profile = context.get_cached(
                "reference_pos_profile",
                lambda: {
                    "NOUN": 0.25,
                    "VERB": 0.20,
                    "ADJ": 0.15,
                    "ADV": 0.10,
                    "DET": 0.10,
                    "ADP": 0.10,
                    "PRON": 0.05,
                    "OTHER": 0.05,
                },
            )

        max_confidence = 0.0
        anomalous_segments = []

        for segment in analysis.transcript.segments:
            text = " ".join(s.text for s in segment.sentences)

            try:
                # Servisten POS dağılımı ve n-gramları al
                pos_dist = context.spacy_pipeline.get_pos_distribution(text)
                pos_ngrams = {
                    n: context.spacy_pipeline.get_pos_ngrams(text, n)
                    for n in self._config.ngram_weights.keys()
                }
            except Exception:
                continue

            if sum(pos_dist.values()) < self._config.min_tokens:
                continue

            total_divergence = 0.0
            total_weight = 0.0

            for n, weight in self._config.ngram_weights.items():
                ngrams = pos_ngrams.get(n, [])
                if not ngrams:
                    continue

                observed_counts = Counter(ngrams)
                total = sum(observed_counts.values())

                # Gözlemlenen ve beklenen dağılımları oluştur
                observed = [
                    observed_counts.get(tag, 0) / total for tag in set(observed_counts)
                ]
                # Basitleştirilmiş: POS profili üzerinden beklenen değeri tahmin et
                expected = [
                    ref_profile.get(tag, 0.05) if isinstance(tag, str) else 0.05
                    for tag in set(observed_counts)
                ]

                if len(observed) == len(expected) and sum(expected) > 0:
                    kl = StatisticalUtils.kl_divergence(observed, expected)
                    total_divergence += kl * weight
                    total_weight += weight

            if total_weight > 0:
                avg_divergence = total_divergence / total_weight
                confidence = ConfidenceCalculator.from_kl_divergence(
                    avg_divergence, expected_max=3.0
                )

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
            description="POS n-gram dağılımı çeviri yapaylığına işaret ediyor.",
            affected_segments=anomalous_segments,
            metadata={
                "divergence_method": "KL",
                "ngram_levels": list(self._config.ngram_weights.keys()),
            },
        )
