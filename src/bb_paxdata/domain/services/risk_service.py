"""Risk assessment service with SBI and DKI calculations.

This service implements risk assessment using the Söylemsel Baskı İndeksi (SBI)
and Diplomatik Konum İndeksi (DKI) formulas. It provides comprehensive risk
analysis for diplomatic discourse segments.
"""

from typing import Any, ClassVar

from ...application.protocols import (
    BaseService,
    NERServiceProtocol,
    RiskAssessment,
    RiskServiceProtocol,
)
from ...domain.enums import RiskLevel
from ..models.segment import Segment
from ..models.sentence import Sentence


class RiskService(BaseService, RiskServiceProtocol):
    """Service for risk assessment with SBI and DKI calculations."""

    # Risk signal keywords (from DatabaseBuilder_v5_8.py)
    RISK_SIGNALS: ClassVar[list[str]] = [
        "unacceptable",
        "red line",
        "cannot tolerate",
        "will not accept",
        "serious consequences",
        "escalate",
        "retaliate",
        "breakdown",
        "collapse",
        "ultimatum",
        "provocation",
        "violation",
        "condemn",
        "denounce",
        "reject outright",
        "military option",
        "unprovoked war",
        "decisive actions",
        "deep strikes",
        "imposed solutions",
        "dismantlement",
        "zero-sum",
        "paralyze",
        "paralyzed",
        "weaponized",
        "breached",
    ]

    # Risk severity mapping
    RISK_SEVERITY: ClassVar[dict[str, RiskLevel]] = {
        "low": RiskLevel.LOW,
        "medium": RiskLevel.MEDIUM,
        "high": RiskLevel.HIGH,
        "critical": RiskLevel.CRITICAL,
    }

    def __init__(self, ner_service: NERServiceProtocol | None = None) -> None:
        """Initialize the risk service.

        Args:
            ner_service: Optional NER service for contextual risk analysis
        """
        super().__init__()
        self._ner_service = ner_service

    def analyze(self, segment: Segment, **kwargs: Any) -> Any:
        """Assess risk in a segment.

        Args:
            segment: The segment to analyze
            **kwargs: Additional analysis parameters

        Returns:
            RiskAssessment containing risk analysis
        """
        return self.assess_risk(segment)

    def compute_sbi(
        self, power_level: float, demand_weight: float, risk_score: float
    ) -> float:
        """Calculate Söylemsel Baskı İndeksi (SBI).

        Formula: (power_level * demand_weight) / 2.0 + risk_score

        Args:
            power_level: Speaker's power level (0-10)
            demand_weight: Weight of the demand (0-1)
            risk_score: Base risk score (0-10)

        Returns:
            SBI score
        """
        return (power_level * demand_weight) / 2.0 + risk_score

    def compute_dki(
        self, norm_diplo: float, norm_risk: float, norm_demand: float, norm_manip: float
    ) -> float:
        """Calculate Diplomatik Konum İndeksi (DKI).

        Formula: norm_diplo*0.4 + (1-norm_risk)*0.3 + norm_demand*0.2
        Formula (cont): + (1-norm_manip)*0.1
        Then: *2 - 1

        Args:
            norm_diplo: Normalized diplomatic score (0-1)
            norm_risk: Normalized risk score (0-1)
            norm_demand: Normalized demand score (0-1)
            norm_manip: Normalized manipulation score (0-1)

        Returns:
            DKI score (-1 to 1)
        """
        base_score = (
            norm_diplo * 0.4
            + (1 - norm_risk) * 0.3
            + norm_demand * 0.2
            + (1 - norm_manip) * 0.1
        )
        return (base_score * 2) - 1

    def contextual_risk(
        self, text: str, entities: dict[str, list[str]] | None = None
    ) -> float:
        """Calculate contextual risk based on NER entities and text content.

        Args:
            text: Text to analyze
            entities: Optional pre-extracted entities

        Returns:
            Contextual risk score (0-10)
        """
        base_risk = 0.0

        # Check for risk signals in text
        text_lower = text.lower()
        signal_count = sum(1 for signal in self.RISK_SIGNALS if signal in text_lower)
        base_risk += signal_count * 2.0

        # Entity-based risk adjustment
        if entities or self._ner_service:
            if not entities and self._ner_service:
                entities = self._ner_service.extract_entities(text)

            if entities:
                # High-risk entities
                high_risk_entities = {
                    "GPE": ["syria", "ukraine", "gaza", "palestine"],
                    "ORG": ["nato", "military", "army"],
                    "PERSON": ["putin", "netanyahu", "erdogan"],
                }

                for entity_type, entity_list in entities.items():
                    if entity_type in high_risk_entities:
                        for entity in entity_list:
                            if entity.lower() in high_risk_entities[entity_type]:
                                base_risk += 1.5

        # Normalize to 0-10 range
        return min(10.0, base_risk)

    def risk_detect(self, text: str) -> tuple[float, list[str]]:
        """Detect risk signals and calculate base risk score.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (risk_score, detected_signals)
        """
        text_lower = text.lower()
        detected_signals = []

        # Check for risk signals
        for signal in self.RISK_SIGNALS:
            if signal in text_lower:
                detected_signals.append(signal)

        # Calculate base risk score
        risk_score = len(detected_signals) * 1.5  # Each signal adds 1.5 points

        # Additional risk factors
        if any(
            word in text_lower for word in ["war", "conflict", "attack", "military"]
        ):
            risk_score += 2.0
        if any(word in text_lower for word in ["nuclear", "weapon", "destruction"]):
            risk_score += 3.0
        if any(word in text_lower for word in ["sanction", "punish", "retaliate"]):
            risk_score += 1.0

        return min(10.0, risk_score), detected_signals

    def _normalize_value(
        self, value: float, min_val: float = 0.0, max_val: float = 10.0
    ) -> float:
        """Normalize a value to 0-1 range.

        Args:
            value: Value to normalize
            min_val: Minimum possible value
            max_val: Maximum possible value

        Returns:
            Normalized value (0-1)
        """
        if max_val <= min_val:
            return 0.0
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

    def _classify_risk_severity(self, risk_score: float) -> RiskLevel:
        """Classify risk severity based on score.

        Args:
            risk_score: Risk score (0-10)

        Returns:
            Risk level
        """
        if risk_score >= 8.0:
            return RiskLevel.CRITICAL
        elif risk_score >= 6.5:
            return RiskLevel.CRITICAL
        elif risk_score >= 4.5:
            return RiskLevel.HIGH
        elif risk_score >= 2.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def assess_risk(self, segment: Segment) -> RiskAssessment:
        """Assess risk level of a segment.

        Args:
            segment: The segment to assess

        Returns:
            RiskAssessment containing risk scores and severity
        """
        # Collect all sentences in segment
        sentences = segment.sentences if hasattr(segment, "sentences") else []

        if not sentences:
            # Fallback to segment text
            text = segment.text if hasattr(segment, "text") else ""
            sentences = [
                Sentence(
                    id="temp",
                    text=text,
                    speaker_id=None,
                    segment_id=None,
                    start_time=None,
                    end_time=None,
                    duration=None,
                    sentiment=None,
                    sentiment_score=None,
                    negation_aware_diplo=None,
                    tension_level=None,
                    negation_type=None,
                    hedging_type=None,
                    hedging_score=None,
                    politeness_act=None,
                    politeness_ratio=None,
                    diplomatic_tone=None,
                    appraisal_attitude=None,
                    dominant_topic=None,
                    topic_specificity=None,
                    topic_scores=None,
                    dominant_frame=None,
                    evidence_types=None,
                    audience_type=None,
                    face_threat_count=None,
                    face_save_count=None,
                    word_count=None,
                    confidence_score=None,
                )
            ]

        # Aggregate risk analysis across sentences
        total_risk_score = 0.0
        all_risk_signals = []
        power_levels = []
        demand_weights = []

        for sentence in sentences:
            # Base risk detection
            risk_score, signals = self.risk_detect(sentence.text)
            total_risk_score += risk_score
            all_risk_signals.extend(signals)

            # Extract power level (from speaker metadata if available)
            power_level = 5.0  # Default medium power
            if hasattr(segment, "speaker") and hasattr(segment.speaker, "power_level"):
                power_level = float(segment.speaker.power_level)
            power_levels.append(power_level)

            # Estimate demand weight based on language
            demand_weight = 0.5  # Default
            text_lower = sentence.text.lower()
            if any(
                word in text_lower for word in ["must", "require", "demand", "insist"]
            ):
                demand_weight = 0.9
            elif any(word in text_lower for word in ["should", "ought", "recommend"]):
                demand_weight = 0.7
            elif any(word in text_lower for word in ["suggest", "propose", "consider"]):
                demand_weight = 0.5
            demand_weights.append(demand_weight)

        # Calculate averages
        avg_risk_score = total_risk_score / len(sentences) if sentences else 0.0
        avg_power_level = sum(power_levels) / len(power_levels) if power_levels else 5.0
        avg_demand_weight = (
            sum(demand_weights) / len(demand_weights) if demand_weights else 0.5
        )

        # Calculate SBI
        sbi_score = self.compute_sbi(avg_power_level, avg_demand_weight, avg_risk_score)

        # Calculate DKI (using normalized values)
        norm_diplo = self._normalize_value(
            5.0 - avg_risk_score
        )  # Inverse risk as diplomatic
        norm_risk = self._normalize_value(avg_risk_score)
        norm_demand = self._normalize_value(avg_demand_weight * 10)  # Scale to 0-10
        norm_manip = self._normalize_value(3.0)  # Default manipulation score

        dki_score = self.compute_dki(norm_diplo, norm_risk, norm_demand, norm_manip)

        # Get contextual risk
        segment_text = " ".join([s.text for s in sentences])
        entities = None
        if self._ner_service:
            entities = self._ner_service.extract_entities(segment_text)
        contextual_risk_score = self.contextual_risk(segment_text, entities)

        # Final risk score (blend of different metrics)
        final_risk_score = (
            avg_risk_score * 0.4 + contextual_risk_score * 0.3 + (sbi_score / 10) * 0.3
        )  # Normalize SBI to 0-10

        # Classify severity
        severity = self._classify_risk_severity(final_risk_score)

        # Remove duplicate risk signals
        unique_signals = list(set(all_risk_signals))

        # Calculate confidence based on signal consistency
        confidence = min(1.0, len(unique_signals) / 5.0) if unique_signals else 0.3

        return RiskAssessment(
            sbi_score=sbi_score,
            dki_score=dki_score,
            risk_score=final_risk_score,
            risk_signals=unique_signals,
            severity=severity,
            confidence=confidence,
        )
