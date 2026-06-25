from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.risk_signal import RiskSignal


class RiskFormula(StrEnum):
    MAX = "max"
    WEIGHTED_AVG = "weighted_avg"
    SUM = "sum"


class DeterministicRiskScorer:
    """
    Phase 1 sonuçlarından LLM bypass kararı için tek skor üretir.
    """

    @staticmethod
    def calculate(
        risk_signals: Sequence[RiskSignal],
        formula: RiskFormula = RiskFormula.MAX,
        negation_dampening: float = 0.3,  # Negation bulunursa skor çarpanı
    ) -> float:
        if not risk_signals:
            return 0.0

        base_score = 0.0

        if formula == RiskFormula.MAX:
            base_score = max(
                (s.credibility_score * s.escalation_multiplier for s in risk_signals),
                default=0.0,
            )
        elif formula == RiskFormula.WEIGHTED_AVG:
            total_weight = float(len(risk_signals))
            if total_weight == 0:
                return 0.0
            base_score = (
                sum(s.credibility_score * s.escalation_multiplier for s in risk_signals)
                / total_weight
            )
        elif formula == RiskFormula.SUM:
            base_score = sum(
                s.credibility_score * s.escalation_multiplier for s in risk_signals
            )
            # Normalize et ki 1.0'ı aşmasın
            base_score = min(base_score, 1.0)

        # Negation dampening uygula (e.g., "not a threat")
        # negation_dampening 0.3 ise skor %70 azalır
        # Bu değer Phase 1 negation detector'dan gelir
        return round(base_score * (1.0 - negation_dampening), 4)
