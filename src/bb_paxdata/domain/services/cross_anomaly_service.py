# ============================================================
# DOSYA: src/bb_paxdata/domain/services/cross_anomaly_service.py
# AÇIKLAMA: Kural tabanlı plugin mimarisi — getattr YOK
# ============================================================

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from ...core.config import settings
from ..enums import NegationType, RiskLevel
from ..models.analysis import Analysis
from ..models.negation_cue import NegationCue
from .protocols import AnomalyResult

logger = logging.getLogger(__name__)


@runtime_checkable
class AnomalyRule(Protocol):
    """
    Her anomali kuralının implement etmesi gereken arayüz.
    Yeni kural eklemek için bu Protocol'u karşılayan bir sınıf yazmak yeterli.
    """

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        """(tetiklendi_mi, anomali_skoru_katkısı, flag_mesajı) döner."""
        ...


class SentimentRiskDivergenceRule:
    """
    Tsytsarau (2017) contradiction measure 'C' formülünü kullanarak
    duygu-risk çelişkisini tespit eder.

    Reference:
        - Tsytsarau, M. et al. (2017). Identifying Sentiment-based Contradictions.
          C = (n·M₂ − M₁²) / ((ϑ·n² + M₁²)·W)
    """

    THETA = 0.1
    THRESHOLD = 0.1

    def __init__(self) -> None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        self._vader = SentimentIntensityAnalyzer()

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        # AI verisi yoksa bu kural sessizce atlanır
        if not analysis.has_ai_output:
            return False, 0.0, ""

        sentences = analysis.sentences
        if not sentences:
            return False, 0.0, ""

        # Her cümle için polarity (VADER compound) hesapla
        polarities = [self._vader.polarity_scores(s)["compound"] for s in sentences]
        n = len(polarities)

        # Moment hesaplamaları
        m1 = sum(polarities) / n
        m2 = sum(p * p for p in polarities) / n

        # Tsytsarau formülü
        w = float(n)
        numerator = (n * m2) - (m1 * m1)
        denominator = ((self.THETA * n * n) + (m1 * m1)) * w

        c = (numerator / denominator) if denominator != 0 else 0.0

        # Faz 2: Negasyon filtrelemesi
        adjustment = self._compute_negation_adjustment(analysis)
        adjusted_score = max(0.0, c - adjustment)

        # Risk ile birleştirme (Opsiyonel: Tsytsarau sadece sentiment çelişkisidir,
        # ancak kural ismi sentiment-risk diverjansı olduğu için risk skoruyla da ilişkilendirebiliriz)
        risk = analysis.effective_risk

        # Eğer çelişki yüksekse (adjusted_score > THRESHOLD) anomali işaretle
        if adjusted_score > self.THRESHOLD:
            return (
                True,
                round(adjusted_score, 4),
                f"SENTIMENT_RISK_DIVERGENCE: Tsytsarau adjusted_C={adjusted_score:.4f}, risk={risk:.2f}",
            )

        return False, 0.0, ""

    def _compute_negation_adjustment(self, analysis: Analysis) -> float:
        """Negasyon kaynaklı false positive'leri hesapla."""
        if not analysis.negation_cues:
            return 0.0

        total_adjustment = 0.0
        for cue in analysis.negation_cues:
            total_adjustment += self._evaluate_cue_false_positive_risk(cue)

        # Normalize by sentence count
        n = len(analysis.sentences)
        return min(1.0, total_adjustment / n) if n > 0 else 0.0

    def _evaluate_cue_false_positive_risk(self, cue: NegationCue) -> float:
        """Tek bir negasyon cue'yu için false positive risk skoru."""
        if cue.negation_type == NegationType.SEMANTIC and cue.confidence > 0.8:
            return 0.35
        if cue.negation_type == NegationType.SURFACE and not cue.has_scope:
            return 0.25
        if cue.negation_type == NegationType.SYNTACTIC and cue.has_scope:
            return 0.20
        if cue.negation_type == NegationType.SCOPE_WIDE:
            return 0.10
        return 0.0


class HighRiskThresholdRule:
    """AI risk skoru kritik eşiği doğrudan aşıyorsa anomali işaretler."""

    CRITICAL_THRESHOLD = 0.8

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        if not analysis.has_ai_output:
            return False, 0.0, ""

        risk = analysis.effective_risk
        if risk >= self.CRITICAL_THRESHOLD:
            return (
                True,
                risk * 0.6,
                f"HIGH_RISK_THRESHOLD: risk={risk:.2f} >= {self.CRITICAL_THRESHOLD}",
            )
        return False, 0.0, ""


class NegativeSentimentRule:
    """Aşırı negatif duygu tek başına da anomali sinyali olabilir."""

    NEGATIVE_THRESHOLD = -0.7

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        if not analysis.has_ai_output:
            return False, 0.0, ""

        sentiment = analysis.effective_sentiment
        if sentiment <= self.NEGATIVE_THRESHOLD:
            score = abs(sentiment) * 0.3
            return (
                True,
                min(score, 0.3),
                f"EXTREME_NEGATIVE_SENTIMENT: sentiment={sentiment:.2f}",
            )
        return False, 0.0, ""


class PowerAsymmetryAnomalyRule:
    """Güç asimetrisi ve sentiment farkı üzerinden anomali tespiti.

    asymmetry_score > 0.5 + sentiment_delta < -0.3 -> POWER_ASYMMETRY_ANOMALY
    """

    THRESHOLD_ASYMMETRY = 0.5
    THRESHOLD_DELTA = -0.3

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        # Eğer Analysis'te birden fazla power_index varsa (örneğin speaker ve mentioned country)
        # asimetriyi hesapla.
        if len(analysis.power_indices) < 2:
            return False, 0.0, ""

        indices = list(analysis.power_indices.values())
        idx_a = indices[0].total_power_index
        idx_b = indices[1].total_power_index

        raw_diff = abs(idx_a - idx_b)
        max_idx = max(idx_a, idx_b)
        asymmetry = (raw_diff / max_idx) if max_idx > 0 else 0.0

        sentiment = analysis.effective_sentiment

        if asymmetry > self.THRESHOLD_ASYMMETRY and sentiment < self.THRESHOLD_DELTA:
            return (
                True,
                asymmetry * 0.5,
                f"POWER_ASYMMETRY_ANOMALY: asymmetry={asymmetry:.2f}, sentiment={sentiment:.2f}",
            )

        return False, 0.0, ""


class CheapTalkAnomalyRule:
    """Cheap talk anomalisi tespiti (Trager 2010).

    power_weighted_score > threshold + signal_credibility < 0.4 -> CHEAP_TALK_ANOMALY
    """

    THRESHOLD_POWER = 0.1
    THRESHOLD_CREDIBILITY = 0.4

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        # Risk sinyalleri üzerinden credibility ve weighted score hesapla
        if not analysis.risk_signals:
            return False, 0.0, ""

        # Basitleştirilmiş Trager proxy (Analysis üzerinde)
        power = 1.0  # Default
        if analysis.speaker_id in analysis.power_indices:
            power = analysis.power_indices[analysis.speaker_id].total_power_index

        max_multiplier = max(s.escalation_multiplier for s in analysis.risk_signals)
        weighted_score = power * max_multiplier

        # commitment_cost proxy: COSTLY_SIGNAL oranı
        costly_count = sum(
            1
            for s in analysis.risk_signals
            if s.signal_type in ("costly_signal", "red_line")
        )
        credibility = costly_count / len(analysis.risk_signals)

        if (
            weighted_score > self.THRESHOLD_POWER
            and credibility < self.THRESHOLD_CREDIBILITY
        ):
            return (
                True,
                0.4,
                f"CHEAP_TALK_ANOMALY: weighted_score={weighted_score:.2f}, credibility={credibility:.2f}",
            )

        return False, 0.0, ""


class CrossAnomalyService:
    """
    Tüm anomali kurallarını koordine eden servis.
    Plugin mimarisi: rules listesine yeni kural sınıfı eklemek yeterli.
    IMMUTABLE: Analysis nesnesini mutate etmez; AnomalyResult döner.
    """

    def __init__(self, rules: list[AnomalyRule] | None = None):
        self.rules: list[AnomalyRule] = rules or [
            SentimentRiskDivergenceRule(),
            HighRiskThresholdRule(),
            NegativeSentimentRule(),
            PowerAsymmetryAnomalyRule(),
            CheapTalkAnomalyRule(),
        ]

    async def detect(self, analysis: Analysis) -> AnomalyResult:
        """
        Analysis nesnesi üzerinde tüm kuralları çalıştırır.
        Analysis'i mutate ETMEZ — AnomalyResult döner.
        Pipeline bu sonucu model_copy(update=...) ile Analysis'e uygular.
        """
        total_score = 0.0
        triggered_flags: list[str] = []

        # AI çıktısı yoksa kural bazlı anomali hesaplanamaz (mevcut kurallar AI bağımlı)
        # Ancak yine de _determine_risk_level çağrılarak fallback mantığı işletilmeli.
        if analysis.has_ai_output:
            for rule in self.rules:
                triggered, contribution, flag_msg = rule.evaluate(analysis)
                if triggered:
                    total_score += contribution
                    triggered_flags.append(flag_msg)
                    logger.debug(
                        f"Kural tetiklendi [{rule.__class__.__name__}]: {flag_msg}"
                    )
        else:
            triggered_flags.append(
                "NO_AI_OUTPUT: Kural bazlı anomali hesaplaması kısıtlı."
            )

        final_score = round(min(total_score, 1.0), 4)

        # Geçici bir Analysis kopyası üzerinde skoru set et ki _determine_risk_level okuyabilsin
        # (Veya doğrudan skoru parametre olarak geçecek şekilde metodu güncelle)
        temp_analysis = analysis.model_copy(update={"anomaly_score": final_score})
        risk_level = self._determine_risk_level(temp_analysis)

        logger.info(
            f"Anomali tespiti tamamlandı: "
            f"id={analysis.id}, score={final_score}, "
            f"flags={len(triggered_flags)}, risk_level={risk_level}"
        )

        return AnomalyResult(
            score=final_score,
            flags=triggered_flags,
            risk_level=risk_level,
            triggered_count=len(triggered_flags),
        )

    @staticmethod
    def _determine_risk_level(analysis: Analysis) -> RiskLevel:
        """
        Bileşik risk seviyesi hesaplama — Dinamik Ağırlıklandırma.
        AI verisi yoksa anomali tek başına karar verici olur.
        """
        # 1. Durum: AI verisi yoksa (AI çökmüş veya atlanmışsa)
        if not analysis.has_ai_output:
            anomaly = analysis.anomaly_score or 0.0
            # AI yokken anomali skoru tam ağırlıkla hesaba katılır
            composite = anomaly * settings.RISK_FALLBACK_ANOMALY_WEIGHT

            # AI yokken düşük risk yoktur, belirsizlik vardır.
            if composite >= 0.7:
                return RiskLevel.CRITICAL
            elif composite >= 0.4:
                return RiskLevel.HIGH
            elif composite > 0.0:
                return RiskLevel.MEDIUM  # Az da olsa anomali varsa inceleme gerekir
            else:
                return RiskLevel.LOW  # Sistemde veri ve anomali yoksa düşük

        # 2. Durum: AI verisi mevcutsa (Normal operasyon)
        ai_risk = analysis.effective_risk
        anomaly = analysis.anomaly_score or 0.0

        composite = (ai_risk * settings.RISK_AI_WEIGHT) + (
            anomaly * settings.RISK_ANOMALY_WEIGHT
        )

        # Yükseltme mantığı (Escalation): AI düşük dese bile anomali çok yüksekse riski yükselt
        if anomaly >= 0.8 and composite < 0.6:
            composite = 0.65  # HIGH seviyesine düşür
            logger.warning(
                f"Risk escalation applied: AI low but anomaly critical. Composite boosted to {composite}"
            )

        if composite >= 0.8:
            return RiskLevel.CRITICAL
        elif composite >= 0.6:
            return RiskLevel.HIGH
        elif composite >= 0.3:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
