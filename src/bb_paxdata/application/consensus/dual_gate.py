"""
DualGateConsensusLayer — Deterministik + AI anomali kararlarını birleştirir.

Bu katman in-memory çalışır. DB'ye yazmaz. Pipeline'ın DETECT→FINALIZE
geçişinde tek geçiş noktasıdır.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from bb_paxdata.application.domain.models.anomaly import (
    AnomalyResult,
    AnomalyValidationDecision,
    AnomalyValidationResult,
)

logger = logging.getLogger(__name__)


class ConsensusLevel(str, Enum):
    CLEAN = "CLEAN"  # Anomali yok
    SOFT_ANOMALY = "SOFT_ANOMALY"  # Zayıf/şüpheli anomali, log tutulur
    HARD_ANOMALY = "HARD_ANOMALY"  # Kesin anomali, HITL kuyruğuna
    CRITICAL_ANOMALY = "CRITICAL_ANOMALY"  # AI tarafından yükseltildi, acil HITL


@dataclass(frozen=True)
class ConsensusResult:
    """DualGateConsensusLayer'ın nihai çıktısı."""

    level: ConsensusLevel
    coherence_score: float  # 0.0–1.0
    final_reasoning: str
    send_to_hitl: bool
    deterministic_result: AnomalyResult
    ai_result: AnomalyValidationResult


class DualGateConsensusLayer:
    """
    Kullanım:
        layer = DualGateConsensusLayer()
        consensus = layer.decide(
            deterministic=anomaly_result,
            ai_validation=ai_result,
        )
        if consensus.send_to_hitl:
            await hitl_queue.enqueue(sentence, consensus)
    """

    # Coherence score eşikleri
    HIGH_COHERENCE_THRESHOLD = 0.75
    LOW_COHERENCE_THRESHOLD = 0.35

    def decide(
        self,
        deterministic: AnomalyResult,
        ai_validation: AnomalyValidationResult,
    ) -> ConsensusResult:
        """Consensus matrisi uygula ve sonuç üret."""
        level = self._apply_matrix(deterministic, ai_validation)
        coherence = self._compute_coherence(deterministic, ai_validation)
        send_to_hitl = level in (
            ConsensusLevel.HARD_ANOMALY,
            ConsensusLevel.CRITICAL_ANOMALY,
        )

        reasoning = (
            f"[DET:{deterministic.has_anomaly}|AI:{ai_validation.decision.value}] "
            f"→ {level.value} | coherence={coherence:.3f} | "
            f"AI reasoning: {ai_validation.reasoning}"
        )

        logger.info(
            "Consensus decision",
            extra={
                "level": level.value,
                "coherence": coherence,
                "send_to_hitl": send_to_hitl,
            },
        )

        return ConsensusResult(
            level=level,
            coherence_score=coherence,
            final_reasoning=reasoning,
            send_to_hitl=send_to_hitl,
            deterministic_result=deterministic,
            ai_result=ai_validation,
        )

    @staticmethod
    def _apply_matrix(
        det: AnomalyResult,
        ai: AnomalyValidationResult,
    ) -> ConsensusLevel:
        d = det.has_anomaly
        v = ai.decision

        if d and v == AnomalyValidationDecision.CONFIRMED:
            return ConsensusLevel.HARD_ANOMALY
        if d and v == AnomalyValidationDecision.ESCALATED:
            return ConsensusLevel.CRITICAL_ANOMALY
        if d and v == AnomalyValidationDecision.DISMISSED:
            return ConsensusLevel.SOFT_ANOMALY
        if d and v == AnomalyValidationDecision.INCONCLUSIVE:
            return ConsensusLevel.SOFT_ANOMALY
        if not d and v == AnomalyValidationDecision.AI_ONLY:
            return ConsensusLevel.SOFT_ANOMALY
        if not d and v == AnomalyValidationDecision.CONFIRMED:
            # AI found something deterministic missed
            return ConsensusLevel.HARD_ANOMALY
        # CLEAN: not d AND (DISMISSED or INCONCLUSIVE)
        return ConsensusLevel.CLEAN

    def _compute_coherence(
        self,
        det: AnomalyResult,
        ai: AnomalyValidationResult,
    ) -> float:
        """
        Coherence Score hesaplama:
        - AI'nın kendi confidence'ı baz alınır
        - Deterministik & AI uyuşuyorsa bonus eklenir
        - Çelişki durumunda penaltı uygulanır
        """
        base = ai.coherence_score
        if det.has_anomaly and ai.decision == AnomalyValidationDecision.CONFIRMED:
            # Her iki kapı da uyuştu → yüksek güven
            return min(1.0, base * 1.1)
        if det.has_anomaly and ai.decision == AnomalyValidationDecision.DISMISSED:
            # Çelişki → güven düşer
            return base * 0.7
        if ai.decision == AnomalyValidationDecision.INCONCLUSIVE:
            return 0.5  # Belirsiz durum ortada
        return base
