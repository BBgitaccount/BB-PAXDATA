from __future__ import annotations

import math
import statistics
from typing import TYPE_CHECKING

import structlog
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from bb_paxdata.domain.enums.sentiment_polarity import SentimentPolarity
from bb_paxdata.domain.models.sentiment_result import (
    EnsembleSentiment,
    ModelSentiment,
)

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class EnsembleSentimentService:
    """Bonacchi (2024) multi-method ensemble sentiment analizi.

    VADER (rule-based) + BERT (transformer) + Flair (sequence)
    modellerinin majority voting ile birleştirilmesi.

    Reference:
        - Bonacchi, C. et al. (2024). Political Uses of the Ancient Past
          on Social Media are Predominantly Negative and Extreme. PLOS ONE.
        - Hutto, C.J. & Gilbert, E.E. (2014). VADER (Faz 1 aktif).
    """

    def __init__(
        self,
        vader_weight: float = 0.3,
        bert_weight: float = 0.4,
        flair_weight: float = 0.3,
        agreement_threshold: float = 0.6,
    ) -> None:
        """Initialize ensemble servisi.

        Args:
            vader_weight: VADER model ağırlığı.
            bert_weight: BERT model ağırlığı.
            flair_weight: Flair model ağırlığı.
            agreement_threshold: Majority voting eşiği.
        """
        total_weight = vader_weight + bert_weight + flair_weight
        if not math.isclose(total_weight, 1.0):
            # Ağırlıkları normalize edelim
            vader_weight /= total_weight
            bert_weight /= total_weight
            flair_weight /= total_weight

        self.weights = {
            "vader": vader_weight,
            "bert": bert_weight,
            "flair": flair_weight,
        }
        self.agreement_threshold = agreement_threshold
        self._vader = SentimentIntensityAnalyzer()
        # self._bert = pipeline("sentiment-analysis", model="...")
        # self._flair = TextClassifier.load("...")

    def _get_vader_score(self, text: str) -> ModelSentiment:
        """VADER compound skoru üretir."""
        scores = self._vader.polarity_scores(text)
        compound = scores["compound"]
        return ModelSentiment(
            model_name="vader",
            compound_score=compound,
            polarity=self._score_to_polarity(compound),
            confidence=abs(compound),  # Basit güven: |compound|
        )

    def _get_bert_score(self, text: str) -> ModelSentiment:
        """BERT sentiment skoru üretir (Mock Faz 1)."""
        # Faz 1'de mock implementasyon; Faz 5'te tam BERT entegrasyonu
        base = self._vader.polarity_scores(text)["compound"]
        noise = 0.0
        compound = max(-1.0, min(1.0, base + noise))
        return ModelSentiment(
            model_name="bert",
            compound_score=compound,
            polarity=self._score_to_polarity(compound),
            confidence=abs(compound) * 0.9,  # BERT daha az "kendinden emin" mock
        )

    def _get_flair_score(self, text: str) -> ModelSentiment:
        """Flair sentiment skoru üretir (Mock Faz 1)."""
        # Faz 1'de mock implementasyon
        base = self._vader.polarity_scores(text)["compound"]
        noise = 0.0
        compound = max(-1.0, min(1.0, base + noise))
        return ModelSentiment(
            model_name="flair",
            compound_score=compound,
            polarity=self._score_to_polarity(compound),
            confidence=abs(compound) * 0.85,
        )

    @staticmethod
    def _score_to_polarity(score: float) -> SentimentPolarity:
        """Compound skoru polariteye çevirir."""
        if score > 0.05:
            return SentimentPolarity.POSITIVE
        elif score < -0.05:
            return SentimentPolarity.NEGATIVE
        else:
            return SentimentPolarity.NEUTRAL

    async def analyze(self, text: str) -> EnsembleSentiment:
        """Ensemble sentiment analizi yapar.

        Args:
            text: Analiz edilecek metin.

        Returns:
            EnsembleSentiment: Majority voting sonucu.
        """
        # Individual model skorları
        vader = self._get_vader_score(text)
        bert = self._get_bert_score(text)
        flair = self._get_flair_score(text)

        votes = [vader, bert, flair]

        # Majority voting
        polarities = [v.polarity for v in votes]
        polarity_counts: dict[SentimentPolarity, int] = {}
        for p in polarities:
            polarity_counts[p] = polarity_counts.get(p, 0) + 1

        max_count = max(polarity_counts.values())
        majority_polarity = max(polarity_counts, key=lambda k: polarity_counts[k])

        # Eğer majority yoksa (1-1-1 bölünme), weighted average kullan
        if max_count < 2:
            method = "weighted_average"
            final_score = sum(
                v.compound_score * self.weights[v.model_name] for v in votes
            )
            final_polarity = self._score_to_polarity(final_score)
        else:
            method = "majority_voting"
            # Majority polariteye sahip modellerin ağırlıklı ortalaması
            majority_votes = [v for v in votes if v.polarity == majority_polarity]
            majority_weights = sum(self.weights[v.model_name] for v in majority_votes)
            if majority_weights == 0:
                final_score = 0.0
            else:
                final_score = (
                    sum(
                        v.compound_score * self.weights[v.model_name]
                        for v in majority_votes
                    )
                    / majority_weights
                )
            final_polarity = majority_polarity

        # Agreement score: polarite çeşitliliğine göre
        unique_polarities = len(set(polarities))
        if unique_polarities == 1:
            agreement = 1.0
        elif unique_polarities == 2:
            agreement = 0.5
        else:
            agreement = 0.0

        # Confidence: agreement × average individual confidence
        avg_confidence = statistics.mean(v.confidence for v in votes)
        confidence = agreement * avg_confidence

        return EnsembleSentiment(
            final_score=round(final_score, 6),
            final_polarity=final_polarity,
            model_votes=tuple(votes),
            agreement_score=round(agreement, 6),
            confidence=round(confidence, 6),
            method=method,
        )
