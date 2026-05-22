from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class ModalCollapseConfig:
    """Modal Collapse kuralı için konfigürasyon."""

    risk_threshold: float = 0.8
    hedging_threshold: float = 0.0


class ModalCollapseRule(BaseAnomalyRule):
    """
    ID: RULE_MODAL_COLLAPSE
    Mantık: Risk skoru > 0.8 olan bir önermede hedging skoru tam olarak 0 ise anomali.
           Kritik bir konuda yumuşatma ifadesi eksikliği.
    """

    def __init__(self, config: ModalCollapseConfig | None = None):
        self._config = config or ModalCollapseConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_MODAL_COLLAPSE"

    @property
    def rule_name(self) -> str:
        return "Modal Collapse (Kiplik Çökmesi)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.HIGH

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        max_confidence = 0.0
        anomalous_segments = []
        max_risk = 0.0

        for segment in analysis.transcript.segments:
            for sentence in segment.sentences:
                try:
                    # Risk ve Hedging servislerinden skorları al
                    if hasattr(context.risk_service, "calculate_risk"):
                        risk = context.risk_service.calculate_risk(sentence.text)
                    else:
                        risk_res = context.risk_service.assess_risk(segment, [sentence])
                        if isinstance(risk_res, (int, float)):
                            risk = float(risk_res) / 10.0
                        elif isinstance(risk_res, dict):
                            risk = float(risk_res.get("risk_score", 0.0)) / 10.0
                        else:
                            risk = float(getattr(risk_res, "risk_score", 0.0)) / 10.0

                    if hasattr(context.hedging_service, "detect_hedging"):
                        hedging = context.hedging_service.detect_hedging(sentence.text)
                    else:
                        hedging_res = context.hedging_service.analyze_hedging(
                            sentence.text
                        )
                        if isinstance(hedging_res, (int, float)):
                            hedging = float(hedging_res)
                        elif isinstance(hedging_res, dict):
                            hedging = float(hedging_res.get("score", 0.0))
                        else:
                            hedging = float(getattr(hedging_res, "score", 0.0))
                except Exception:
                    continue

                if (
                    risk > self._config.risk_threshold
                    and hedging <= self._config.hedging_threshold
                ):
                    # Risk skoru 0.8 üzerindeki mesafeye göre confidence ölçekle
                    extra = risk - self._config.risk_threshold
                    confidence = min(1.0, 0.85 + (extra * 0.75))

                    if confidence > max_confidence:
                        max_confidence = confidence
                        max_risk = risk
                        anomalous_segments = [
                            SegmentRef(
                                segment_id=segment.segment_id,
                                start_time=segment.start_time,
                                end_time=segment.end_time,
                            )
                        ]

        if not anomalous_segments:
            return None

        # Risk çok yüksekse şiddeti artır
        severity = AnomalySeverity.CRITICAL if max_risk > 0.9 else self.severity

        return AnomalyResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=severity,
            confidence_score=max_confidence,
            description=f"Yüksek riskli önermede ({max_risk:.2f}) hedging tespiti yapılamadı.",
            affected_segments=anomalous_segments,
            metadata={"max_risk": max_risk, "hedging": 0.0},
        )
