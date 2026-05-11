"""Cross-anomaly detection service for diplomatic discourse analysis.

This service detects cross-anomalies by comparing AI analysis results with
formula-based calculations. It identifies contradictions and inconsistencies
that may indicate manipulation, deception, or unusual diplomatic patterns.

Formula alignment with AIanalyst_v5_8.py detect_cross_anomalies():
- Anomaly 2: ai_sent <= -0.5 AND ai_tone == 'confrontational' (NO power filter)
- Anomaly 3: ai_sent >= 0.3 AND ai_tone == 'confrontational' (velvet glove:
  positive sentiment paradox, NOT politeness×risk combination)
"""

from typing import Any, ClassVar

from ...application.protocols import (
    AnomalyResult,
    BaseService,
    CrossAnomalyServiceProtocol,
)
from ..enums import AnomalySeverity, AnomalyType
from ..models.analysis import Analysis


class CrossAnomalyService(BaseService, CrossAnomalyServiceProtocol):
    """Service for detecting cross-anomalies in diplomatic discourse analysis."""

    # Anomaly detection thresholds (from AIanalyst_v5_8.py)
    ANOMALY_RISK_HIGH: ClassVar[float] = 7
    ANOMALY_HEDGE_HIGH: ClassVar[float] = 0.6
    ANOMALY_HEDGE_LOW: ClassVar[float] = 0.2
    ANOMALY_MANIP_HIGH: ClassVar[float] = 0.7
    ANOMALY_MANIP_MED: ClassVar[float] = 0.5
    ANOMALY_SENT_NEG: ClassVar[float] = -0.5
    ANOMALY_SENT_POS: ClassVar[float] = 0.3
    ANOMALY_POWER_HIGH: ClassVar[float] = 8
    ANOMALY_RISK_MED: ClassVar[float] = 6
    ANOMALY_HEDGE_MED: ClassVar[float] = 0.55

    def __init__(self) -> None:
        """Initialize the cross-anomaly service."""
        super().__init__()

    def analyze(self, analysis: Analysis, **kwargs: Any) -> Any:
        """Detect cross-anomalies in analysis results.

        Args:
            analysis: The analysis results to check for anomalies
            **kwargs: Additional analysis parameters

        Returns:
            List of detected anomalies
        """
        return self.detect_anomalies(analysis)

    def detect_anomalies(self, analysis: Analysis) -> list[AnomalyResult]:
        """Detect cross-anomalies in analysis results.

        Args:
            analysis: The analysis results to check for anomalies

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Extract values from analysis
        ai_values = self._extract_ai_values(analysis)
        formula_values = self._extract_formula_values(analysis)

        # Detect each type of anomaly
        anomalies.extend(self._detect_risk_hedging_conflict(ai_values, formula_values))
        anomalies.extend(
            self._detect_negative_confrontational_amplification(
                ai_values, formula_values
            )
        )
        anomalies.extend(
            self._detect_velvet_glove_confrontation(ai_values, formula_values)
        )
        anomalies.extend(
            self._detect_high_risk_conciliatory_mask(ai_values, formula_values)
        )
        anomalies.extend(
            self._detect_direct_manipulation_low_hedge(ai_values, formula_values)
        )
        anomalies.extend(
            self._detect_dominant_actor_pressure(ai_values, formula_values)
        )
        anomalies.extend(
            self._detect_vague_demand_plausible_deniability(ai_values, formula_values)
        )
        anomalies.extend(
            self._detect_conflict_frame_positive_wrap(ai_values, formula_values)
        )
        anomalies.extend(
            self._detect_inconsistency_plus_manipulation(ai_values, formula_values)
        )
        anomalies.extend(
            self._detect_negative_appraisal_persuasive_tone(ai_values, formula_values)
        )

        return anomalies

    def _extract_ai_values(self, analysis: Analysis) -> dict[str, Any]:
        """Extract AI-derived values from analysis.

        Args:
            analysis: Analysis object

        Returns:
            Dictionary of AI values
        """
        # These would be populated by AI analysis
        return {
            "ai_sentiment": getattr(analysis, "ai_sentiment_score", 0.0),
            "ai_risk": getattr(analysis, "ai_risk_score", 0.0),
            "ai_hedging": getattr(analysis, "ai_hedging_score", 0.0),
            "ai_manipulation": getattr(analysis, "ai_manipulation_score", 0.0),
            "ai_politeness": getattr(analysis, "ai_politeness_score", 0.0),
            "ai_diplomatic_tone": getattr(analysis, "ai_diplomatic_tone", "neutral"),
            "ai_frame": getattr(analysis, "ai_frame_type", "neutral"),
            "ai_appraisal": getattr(analysis, "ai_appraisal_attitude", "neutral"),
        }

    def _extract_formula_values(self, analysis: Analysis) -> dict[str, Any]:
        """Extract formula-derived values from analysis.

        Args:
            analysis: Analysis object

        Returns:
            Dictionary of formula values
        """
        # These would be calculated by domain services
        return {
            "formula_sentiment": getattr(analysis, "sentiment_score", 0.0),
            "formula_risk": getattr(analysis, "risk_score", 0.0),
            "formula_hedging": getattr(analysis, "hedging_score", 0.0),
            "formula_manipulation": getattr(analysis, "manipulation_score", 0.0),
            "power_level": getattr(analysis, "speaker_power", 5.0),
            "sbi_score": getattr(analysis, "sbi_score", 0.0),
            "dki_score": getattr(analysis, "dki_score", 0.0),
        }

    def _detect_risk_hedging_conflict(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect risk-hedging conflict anomalies.

        High risk language with high hedging indicates potential deception.
        """
        anomalies = []

        ai_risk = ai_values.get("ai_risk", 0.0)
        formula_hedging = formula_values.get("formula_hedging", 0.0)

        if (
            ai_risk >= self.ANOMALY_RISK_HIGH
            and formula_hedging >= self.ANOMALY_HEDGE_HIGH
        ):

            severity = AnomalySeverity.HIGH if ai_risk >= 8 else AnomalySeverity.MEDIUM

            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.RISK_HEDGING_CONFLICT,
                    severity=severity,
                    category="Deception Pattern",
                    description=(
                        "High risk language combined with strong hedging suggests "
                        "potential deception or uncertainty masking"
                    ),
                    ai_values={"ai_risk": ai_risk},
                    formula_values={"formula_hedging": formula_hedging},
                    confidence=0.8,
                )
            )

        return anomalies

    def _detect_negative_confrontational_amplification(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect negative confrontational amplification anomalies.

        Mirrors AIanalyst_v5_8.py Anomali 2:
        - Condition: ai_sentiment <= ANOMALY_SENT_NEG AND ai_tone == 'confrontational'
        - Power level is NOT a filtering condition (any actor can trigger this)
        - Severity: HIGH (all cases)
        """
        anomalies = []

        ai_sentiment = ai_values.get("ai_sentiment", 0.0)
        ai_tone = ai_values.get("ai_diplomatic_tone", "neutral")

        if ai_sentiment <= self.ANOMALY_SENT_NEG and ai_tone == "confrontational":
            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.NEGATIVE_CONFRONTATIONAL_AMPLIFICATION,
                    severity=AnomalySeverity.HIGH,
                    category="agresif_söylem",
                    description=(
                        f"Güçlü negatif duygu ({ai_sentiment:+.3f}) ve yüzleşmeci ton "
                        "birlikte saptandı. Bu kombinasyon açık düşmanca söylemin "
                        "göstergesidir. Diplomatik forumlarda bu düzeyde bir "
                        "kızgınlık-yüzleşme eşzamanlılığı, konuşmacının normları "
                        "kasıtlı olarak zorladığını ve güç projeksiyonu "
                        "yaptığını işaret edebilir."
                    ),
                    ai_values={
                        "ai_sentiment": ai_sentiment,
                        "ai_diplomatic_tone": ai_tone,
                    },
                    formula_values={},
                    confidence=0.9,
                )
            )

        return anomalies

    def _detect_velvet_glove_confrontation(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect velvet glove confrontation anomalies.

        Mirrors AIanalyst_v5_8.py Anomali 3:
        - Condition: ai_sentiment >= ANOMALY_SENT_POS (0.3) AND
                     ai_tone == 'confrontational'
        - Paradox: positive-sounding words + confrontational intent
        - Manipulation score is used to strengthen/weaken the description
          but does NOT gate the anomaly trigger
        """
        anomalies = []

        ai_sentiment = ai_values.get("ai_sentiment", 0.0)
        ai_tone = ai_values.get("ai_diplomatic_tone", "neutral")
        ai_manip = ai_values.get("ai_manipulation", 0.0)

        if ai_sentiment >= self.ANOMALY_SENT_POS and ai_tone == "confrontational":
            manip_note = "güçlendiriyor" if ai_manip >= 0.4 else "henüz desteklemiyor"
            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.VELVET_GLOVE_CONFRONTATION,
                    severity=AnomalySeverity.MEDIUM,
                    category="örtülü_baskı",
                    description=(
                        f"Pozitif duygu ({ai_sentiment:+.3f}) ile yüzleşmeci ton aynı "
                        "anda geliyor. Bu paradoks 'velvet glove' stratejisini işaret "
                        "edebilir: nazik, dostane sözcüklerle kaplı bir baskı mesajı. "
                        f"Manipülasyon skoru ({ai_manip:.2f}) bu yorumu {manip_note}."
                    ),
                    ai_values={
                        "ai_sentiment": ai_sentiment,
                        "ai_diplomatic_tone": ai_tone,
                        "ai_manipulation": ai_manip,
                    },
                    formula_values={},
                    confidence=0.7,
                )
            )

        return anomalies

    def _detect_high_risk_conciliatory_mask(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect high risk conciliatory mask anomalies.

        High risk content with conciliatory diplomatic tone.
        """
        anomalies = []

        ai_risk = ai_values.get("ai_risk", 0.0)
        ai_tone = ai_values.get("ai_diplomatic_tone", "neutral")

        if ai_risk >= self.ANOMALY_RISK_HIGH and ai_tone in [
            "conciliatory",
            "cooperative",
            "peaceful",
        ]:

            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.HIGH_RISK_CONCILIATORY_MASK,
                    severity=AnomalySeverity.HIGH,
                    category="Deception Pattern",
                    description=(
                        "High-risk content masked with conciliatory tone "
                        "suggests strategic positioning"
                    ),
                    ai_values={"ai_risk": ai_risk, "ai_diplomatic_tone": ai_tone},
                    formula_values={},
                    confidence=0.8,
                )
            )

        return anomalies

    def _detect_direct_manipulation_low_hedge(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect direct manipulation with low hedging.

        High manipulation score with low hedging indicates overt manipulation.
        """
        anomalies = []

        ai_manipulation = ai_values.get("ai_manipulation", 0.0)
        formula_hedging = formula_values.get("formula_hedging", 0.0)

        if (
            ai_manipulation >= self.ANOMALY_MANIP_HIGH
            and formula_hedging <= self.ANOMALY_HEDGE_LOW
        ):

            severity = (
                AnomalySeverity.CRITICAL
                if ai_manipulation >= 0.8
                else AnomalySeverity.HIGH
            )

            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.DIRECT_MANIPULATION_LOW_HEDGE,
                    severity=severity,
                    category="Manipulation",
                    description=(
                        "High manipulation score with low hedging indicates "
                        "overt manipulation attempts"
                    ),
                    ai_values={"ai_manipulation": ai_manipulation},
                    formula_values={"formula_hedging": formula_hedging},
                    confidence=0.9,
                )
            )

        return anomalies

    def _detect_dominant_actor_pressure(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect dominant actor pressure anomalies.

        High power actors using pressure tactics.
        """
        anomalies = []

        power_level = formula_values.get("power_level", 5.0)
        sbi_score = formula_values.get("sbi_score", 0.0)
        ai_risk = ai_values.get("ai_risk", 0.0)

        if (
            power_level >= self.ANOMALY_POWER_HIGH
            and sbi_score >= 7.0
            and ai_risk >= self.ANOMALY_RISK_MED
        ):

            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.DOMINANT_ACTOR_PRESSURE,
                    severity=AnomalySeverity.HIGH,
                    category="Power Dynamics",
                    description=(
                        "High-power actor applying significant pressure "
                        "through elevated SBI scores"
                    ),
                    ai_values={"ai_risk": ai_risk},
                    formula_values={"power_level": power_level, "sbi_score": sbi_score},
                    confidence=0.8,
                )
            )

        return anomalies

    def _detect_vague_demand_plausible_deniability(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect vague demands with plausible deniability.

        High hedging with demand language suggests ambiguous positioning.
        """
        anomalies = []

        formula_hedging = formula_values.get("formula_hedging", 0.0)
        ai_risk = ai_values.get("ai_risk", 0.0)

        # Check for demand indicators (this would need more sophisticated detection)
        has_demand_indicators = ai_risk >= 4.0  # Proxy for demand language

        if formula_hedging >= self.ANOMALY_HEDGE_HIGH and has_demand_indicators:

            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.VAGUE_DEMAND_PLAUSIBLE_DENIABILITY,
                    severity=AnomalySeverity.MEDIUM,
                    category="Strategic Ambiguity",
                    description=(
                        "High hedging combined with demand indicators "
                        "suggests strategic ambiguity"
                    ),
                    ai_values={"ai_risk": ai_risk},
                    formula_values={"formula_hedging": formula_hedging},
                    confidence=0.6,
                )
            )

        return anomalies

    def _detect_conflict_frame_positive_wrap(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect conflict frame with positive wrapping.

        Conflict content framed in positive terms.
        """
        anomalies = []

        ai_frame = ai_values.get("ai_frame", "neutral")
        ai_sentiment = ai_values.get("ai_sentiment", 0.0)
        ai_risk = ai_values.get("ai_risk", 0.0)

        if (
            ai_frame in ["conflict", "security", "threat"]
            and ai_sentiment >= self.ANOMALY_SENT_POS
            and ai_risk >= self.ANOMALY_RISK_MED
        ):

            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.CONFLICT_FRAME_POSITIVE_WRAP,
                    severity=AnomalySeverity.MEDIUM,
                    category="Framing Strategy",
                    description=(
                        "Conflict-related content framed in positive terms "
                        "indicates strategic positioning"
                    ),
                    ai_values={
                        "ai_frame": ai_frame,
                        "ai_sentiment": ai_sentiment,
                        "ai_risk": ai_risk,
                    },
                    formula_values={},
                    confidence=0.7,
                )
            )

        return anomalies

    def _detect_inconsistency_plus_manipulation(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect inconsistency combined with manipulation.

        High inconsistency scores with high manipulation indicates deceptive patterns.
        """
        anomalies = []

        ai_manipulation = ai_values.get("ai_manipulation", 0.0)
        # Inconsistency would be calculated from multiple factors
        inconsistency_score = abs(
            ai_values.get("ai_sentiment", 0.0)
            - formula_values.get("formula_sentiment", 0.0)
        )

        if ai_manipulation >= self.ANOMALY_MANIP_MED and inconsistency_score >= 0.5:

            severity = (
                AnomalySeverity.HIGH
                if ai_manipulation >= self.ANOMALY_MANIP_HIGH
                else AnomalySeverity.MEDIUM
            )

            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.INCONSISTENCY_PLUS_MANIPULATION,
                    severity=severity,
                    category="Deception Pattern",
                    description=(
                        "High manipulation combined with inconsistent sentiment "
                        "indicates deceptive communication"
                    ),
                    ai_values={"ai_manipulation": ai_manipulation},
                    formula_values={"inconsistency_score": inconsistency_score},
                    confidence=0.8,
                )
            )

        return anomalies

    def _detect_negative_appraisal_persuasive_tone(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[AnomalyResult]:
        """Detect negative appraisal with persuasive tone.

        Negative judgments combined with persuasive language.
        """
        anomalies = []

        ai_appraisal = ai_values.get("ai_appraisal", "neutral")
        ai_sentiment = ai_values.get("ai_sentiment", 0.0)
        ai_politeness = ai_values.get("ai_politeness", 0.0)

        if (
            ai_appraisal in ["negative", "critical", "disapproving"]
            and ai_sentiment <= self.ANOMALY_SENT_NEG
            and ai_politeness >= 0.6
        ):  # Polite but negative

            anomalies.append(
                AnomalyResult(
                    type=AnomalyType.NEGATIVE_APPRAISAL_PERSUASIVE_TONE,
                    severity=AnomalySeverity.MEDIUM,
                    category="Persuasion Strategy",
                    description=(
                        "Negative appraisal combined with polite persuasive tone "
                        "indicates strategic influence attempt"
                    ),
                    ai_values={
                        "ai_appraisal": ai_appraisal,
                        "ai_sentiment": ai_sentiment,
                        "ai_politeness": ai_politeness,
                    },
                    formula_values={},
                    confidence=0.7,
                )
            )

        return anomalies
