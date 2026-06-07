from __future__ import annotations

from enum import StrEnum


class AnomalyType(StrEnum):
    """CrossAnomalyService tarafından tespit edilen anomali türleri.

    References:
        - Tsytsarau et al. (2017): SENTIMENT_RISK_DIVERGENCE
        - Zagare (2004): Risk escalation multipliers (Faz 3 entegrasyonu)
        - CONTEXT.md Bölüm 4.B: CrossAnomalyService
    """

    SENTIMENT_RISK_DIVERGENCE = "sentiment_risk_divergence"
    """Duygu skoru ile risk skoru arasındaki istatistiksel çelişki.

    Tsytsarau (2017) contradiction measure C formülü ile hesaplanır:
    C = (n·M₂ − M₁²) / ((ϑ·n² + M₁²)·W)

    C > threshold durumunda tetiklenir. Yüksek duygu + yüksek risk
    veya düşük duygu + düşük risk birlikteliği anomalidir.
    """

    # Mevcut değerler (korunur):
    RISK_HEDGING_CONFLICT = "risk_hedging_conflict"
    NEGATIVE_CONFRONTATIONAL_AMPLIFICATION = "negative_confrontational_amplification"
    VELVET_GLOVE_CONFRONTATION = "velvet_glove_confrontation"
    HIGH_RISK_CONCILIATORY_MASK = "high_risk_conciliatory_mask"
    DIRECT_MANIPULATION_LOW_HEDGE = "direct_manipulation_low_hedge"
    DOMINANT_ACTOR_PRESSURE = "dominant_actor_pressure"
    VAGUE_DEMAND_PLAUSIBLE_DENIABILITY = "vague_demand_plausible_deniability"
    CONFLICT_FRAME_POSITIVE_WRAP = "conflict_frame_positive_wrap"
    INCONSISTENCY_PLUS_MANIPULATION = "inconsistency_plus_manipulation"
    NEGATIVE_APPRAISAL_PERSUASIVE_TONE = "negative_appraisal_persuasive_tone"
    POWER_ASYMMETRY_ANOMALY = "power_asymmetry_anomaly"
    CHEAP_TALK_ANOMALY = "cheap_talk_anomaly"

    # Faz 8: Discourse-Kinetic Index (DKI) Anomalileri
    DKI_EXTREME = "dki_extreme"
    """DKI skoru eşik değerin üzerinde (ör: |DKI| > 2.0)."""

    SBI_DKI_DIVERGENCE = "sbi_dki_divergence"
    """SBI (stabilite) ile DKI (velocity) arasındaki çelişki."""

    SEMANTIC_SHIFT_ANOMALY = "semantic_shift_anomaly"
    """Beklenmedik derecede yüksek semantik kayma."""

    LLM_CALIBRATION_DRIFT = "llm_calibration_drift"
    """LLM pozisyon tahmini ile Wordfish arasındaki sapma."""

    @property
    def is_sentiment_related(self) -> bool:
        """Bu anomali türü duygu analizi ile mi ilişkilidir?"""
        return self in {
            AnomalyType.SENTIMENT_RISK_DIVERGENCE,
            # Faz 1+'da eklenebilecek diğer duygu anomalileri...
        }
