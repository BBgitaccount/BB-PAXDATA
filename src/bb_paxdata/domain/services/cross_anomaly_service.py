# ============================================================
# DOSYA: src/bb_paxdata/domain/services/cross_anomaly_service.py
# AÇIKLAMA: Kural tabanlı plugin mimarisi — getattr YOK
# ============================================================

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from ...core.config import settings
from ..enums import RiskLevel
from ..models.analysis import Analysis
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
    Duygu skoru ile risk skoru anlamlı biçimde çelişiyorsa anomali işaretler.
    Örnek: Pozitif duygu ama çok yüksek risk → çelişki.
    """

    DIVERGENCE_THRESHOLD = 0.5

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        # AI verisi yoksa bu kural sessizce atlanır — sahte anomali üretilmez
        if not analysis.has_ai_output:
            return False, 0.0, ""

        sentiment = analysis.effective_sentiment  # -1.0 ile +1.0 arası
        risk = analysis.effective_risk  # 0.0 ile 1.0 arası

        # Pozitif duygu ama yüksek risk → gerçek bir çelişki sinyali
        if sentiment > 0.3 and risk > 0.6:
            divergence_score = (risk - sentiment) * 0.4
            return (
                True,
                min(divergence_score, 0.4),
                f"SENTIMENT_RISK_DIVERGENCE: sentiment={sentiment:.2f}, risk={risk:.2f}",
            )
        return False, 0.0, ""


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
