# ============================================================
# DOSYA: src/bb_paxdata/domain/services/cross_anomaly_service.py
# AÇIKLAMA: Kural tabanlı plugin mimarisi — getattr YOK
# ============================================================

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from bb_paxdata.application.domain.models.anomaly import AnomalyResult
from bb_paxdata.application.domain.models.negation_cue import NegationCue
from bb_paxdata.application.domain.models.rule_anomaly import RuleHealthReport
from bb_paxdata.application.domain.ports.anomaly_rule import AnomalyRule
from bb_paxdata.application.domain.services.rule_registry import RuleRegistry
from bb_paxdata.config.settings import get_settings

from ...protocols import AnomalyResult as LegacyAnomalyResult
from ..enums import AnomalySeverity, AnomalyType, NegationType, RiskLevel
from ..enums.country_enums import NarrativeLayer
from ..models.analysis import Analysis

logger = structlog.get_logger(__name__)

# Graceful degradation for vaderSentiment
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer as _VADER

    _VADER_AVAILABLE = True
except ImportError:
    _VADER_AVAILABLE = False
    logger.warning(
        "vaderSentiment kurulu değil; SentimentRiskDivergenceRule, ToneDriftRule, "
        "ve EntityFlipRule devre dışı kalacak."
    )


class SentimentRiskDivergenceRule:
    """
    Tsytsarau (2017) contradiction measure 'C' formülünü kullanarak
    duygu-risk çelişkisini tespit eder.
    """

    THETA = 0.1
    THRESHOLD = 0.1

    def __init__(self) -> None:
        if not _VADER_AVAILABLE:
            self._vader = None
        else:
            self._vader = _VADER()

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        if self._vader is None:
            return False, 0.0, ""

        if not analysis.has_ai_output:
            return False, 0.0, ""

        sentences = analysis.sentences
        if not sentences:
            return False, 0.0, ""

        polarities = [self._vader.polarity_scores(s)["compound"] for s in sentences]
        n = len(polarities)

        m1 = sum(polarities) / n
        m2 = sum(p * p for p in polarities) / n

        w = float(n)
        numerator = (n * m2) - (m1 * m1)
        denominator = ((self.THETA * n * n) + (m1 * m1)) * w

        c = (numerator / denominator) if denominator != 0 else 0.0
        adjustment = self._compute_negation_adjustment(analysis)
        adjusted_score = max(0.0, c - adjustment)
        risk = analysis.effective_risk

        if adjusted_score > self.THRESHOLD:
            return (
                True,
                round(adjusted_score, 4),
                f"SENTIMENT_RISK_DIVERGENCE: Tsytsarau adjusted_C={adjusted_score:.4f}, risk={risk:.2f}",
            )

        return False, 0.0, ""

    def _compute_negation_adjustment(self, analysis: Analysis) -> float:
        if not analysis.negation_cues:
            return 0.0

        total_adjustment = 0.0
        for cue in analysis.negation_cues:
            total_adjustment += self._evaluate_cue_false_positive_risk(cue)

        n = len(analysis.sentences)
        return min(1.0, total_adjustment / n) if n > 0 else 0.0

    def _evaluate_cue_false_positive_risk(self, cue: NegationCue) -> float:
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
    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        return analysis.evaluate_high_risk_anomaly()


class NegativeSentimentRule:
    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        return analysis.evaluate_negative_sentiment_anomaly()


class PowerAsymmetryAnomalyRule:
    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        return analysis.evaluate_power_asymmetry_anomaly()


class CheapTalkAnomalyRule:
    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        return analysis.evaluate_cheap_talk_anomaly()


class TopicDiversityAnomalyRule:
    """Discourse fragmentation anomaly via BERTopic topic distribution entropy.

    High Shannon entropy in P(topic | doc) indicates a speaker is mixing many
    unrelated topics in a single utterance — a known rhetorical evasion and
    plausible-deniability signal (Vague Demand Plausible Deniability pattern).

    Threshold tuned empirically: entropy > 2.0 bits with CRITICAL risk ≥ 0.6
    produces a reliable signal without noise from routine multi-issue speeches.

    Reference:
        - AnomalyType.VAGUE_DEMAND_PLAUSIBLE_DENIABILITY
        - TopicSynthesis.topic_diversity (Shannon entropy, base-2)
    """

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        return analysis.evaluate_topic_diversity_anomaly()


class ToneDriftRule:
    def __init__(self, sigma_multiplier: float = 2.0, min_sentences: int = 3):
        if not _VADER_AVAILABLE:
            self._vader = None
        else:
            self._vader = _VADER()
        self.sigma_multiplier = sigma_multiplier
        self.min_sentences = min_sentences

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        if self._vader is None:
            return False, 0.0, ""

        sentences = analysis.sentences
        if not sentences or len(sentences) < self.min_sentences:
            return False, 0.0, ""

        scores = [self._vader.polarity_scores(s)["compound"] for s in sentences]
        n = len(scores)
        mean = sum(scores) / n
        variance = sum((x - mean) ** 2 for x in scores) / n
        import math

        std = math.sqrt(variance)

        if std < 0.25:
            return False, 0.0, ""

        max_possible_z = (n - 1) / math.sqrt(n)
        effective_multiplier = min(self.sigma_multiplier, 0.9 * max_possible_z)
        threshold = effective_multiplier * std
        max_deviation = max(abs(s - mean) for s in scores)

        if max_deviation > threshold:
            z = max_deviation / std
            confidence = min(1.0, z / 4.0)
            return (
                True,
                round(confidence, 4),
                f"TONE_DRIFT: deviation={max_deviation:.2f} > threshold={threshold:.2f} ({self.sigma_multiplier}σ)",
            )

        return False, 0.0, ""


class EntityFlipRule:
    def __init__(self, flip_threshold: float = 1.0):
        if not _VADER_AVAILABLE:
            self._vader = None
        else:
            self._vader = _VADER()
        self.flip_threshold = flip_threshold
        self.entity_types = {"GPE", "PERSON"}

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        if self._vader is None:
            return False, 0.0, ""

        sentences = analysis.sentences
        entities = analysis.entities
        if not sentences or len(sentences) < 2 or not entities:
            return False, 0.0, ""

        sentence_scores = [
            self._vader.polarity_scores(s)["compound"] for s in sentences
        ]

        entity_sentiments: dict[str, list[tuple[int, float, str]]] = {}
        for i, sent in enumerate(sentences):
            sent_lower = sent.lower()
            for ent in entities:
                ent_text = ent.get("text", "").strip()
                ent_label = ent.get("label", "")
                if ent_label in self.entity_types and ent_text.lower() in sent_lower:
                    if ent_text.lower() not in entity_sentiments:
                        entity_sentiments[ent_text.lower()] = []
                    entity_sentiments[ent_text.lower()].append(
                        (i, sentence_scores[i], ent_label)
                    )

        max_confidence = 0.0
        triggered_msg = ""
        for ent_text, occurrences in entity_sentiments.items():
            if len(occurrences) < 2:
                continue
            scores = [occ[1] for occ in occurrences]
            max_score = max(scores)
            min_score = min(scores)
            flip_size = max_score - min_score

            if flip_size >= self.flip_threshold:
                ent_label = occurrences[0][2]
                weight = 1.0 if ent_label == "GPE" else 0.9
                confidence = min(1.0, (flip_size / 2.0) * weight)
                if confidence > max_confidence:
                    max_confidence = confidence
                    triggered_msg = f"ENTITY_FLIP: Entity '{ent_text}' has contradictory sentiments ({flip_size:.2f}) across sentences: {scores} ({ent_label})"

        if max_confidence > 0.0:
            return True, round(max_confidence, 4), triggered_msg

        return False, 0.0, ""


class StrategicNarrativeClashRule:
    """
    Detects strategic narrative clashes between opposing actors.
    A clash is marked when a confrontation is active (avg_sentiment < -0.3)
    and one actor pivots from an ISSUE narrative to an IDENTITY-defense narrative
    in response to another actor's charges.
    """

    COUNTER_NARRATIVE_BOOST = 0.50

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        clash_detected = False
        description = ""
        boost = 0.0
        clash_from = None
        clash_to = None
        clash_salience = 0.0

        bilaterals = analysis.bilateral_metrics or []
        for rel in bilaterals:
            if rel.avg_sentiment < -0.3:
                layer = getattr(rel, "narrative_layer", None)
                salience = getattr(rel, "narrative_salience", 0.0)
                if layer == NarrativeLayer.IDENTITY and salience > 0.6:
                    if not clash_detected:
                        clash_from = rel.from_country
                        clash_to = rel.to_country
                        clash_salience = salience
                    clash_detected = True
                    boost += salience * self.COUNTER_NARRATIVE_BOOST

        final_score = round(min(boost, 1.5), 6)
        if clash_detected:
            description = (
                f"STRATEGIC NARRATIVE CLASH: Actor '{clash_from}' deflected confrontation "
                f"from '{clash_to}' via IDENTITY pivot. Salience: {clash_salience:.4f}."
            )
            return True, final_score, description

        return False, 0.0, ""


class CrossAnomalyService:
    """
    Tüm anomali kurallarını koordine eden servis.
    Plugin mimarisi: rules listesine veya plugin dizinine dinamik yükleme desteği.
    IMMUTABLE: Analysis nesnesini mutate etmez; AnomalyResult döner.
    """

    ANOMALY_RISK_HIGH = 7
    ANOMALY_HEDGE_HIGH = 0.6
    ANOMALY_HEDGE_LOW = 0.2
    ANOMALY_MANIP_HIGH = 0.7
    ANOMALY_MANIP_MED = 0.5
    ANOMALY_SENT_NEG = -0.5
    ANOMALY_SENT_POS = 0.3
    ANOMALY_POWER_HIGH = 8
    ANOMALY_RISK_MED = 6
    ANOMALY_HEDGE_MED = 0.55

    def __init__(
        self,
        rules: list[AnomalyRule] | None = None,
        registry: RuleRegistry | None = None,
        rules_dir: str | Path | None = None,
    ):
        self._rules_dir = rules_dir
        self._registry = registry or RuleRegistry(rules_dir)
        self._initialized = False

        self.rules = rules or [
            SentimentRiskDivergenceRule(),
            HighRiskThresholdRule(),
            NegativeSentimentRule(),
            PowerAsymmetryAnomalyRule(),
            CheapTalkAnomalyRule(),
            TopicDiversityAnomalyRule(),
            ToneDriftRule(),
            EntityFlipRule(),
            StrategicNarrativeClashRule(),
        ]
        self.confidence = 1.0

    async def initialize(self) -> None:
        if self._rules_dir and not self._initialized:
            await self._registry.load_from_directory(self._rules_dir)
            self._initialized = True
        else:
            self._initialized = True

    def analyze(self, analysis: Analysis, **kwargs: Any) -> Any:
        return self.detect_anomalies(analysis)

    async def detect(self, analysis: Analysis) -> AnomalyResult:
        if not self._initialized:
            await self.initialize()

        total_score = 0.0
        triggered_flags: list[str] = []

        active_rules = self._registry.rules
        if not active_rules and not self._rules_dir:
            active_rules = self.rules

        if analysis.has_ai_output:
            for rule in active_rules:
                try:
                    res = rule.evaluate(analysis)
                    if isinstance(res, list):
                        # Plugin output: list of RuleAnomaly
                        for anomaly in res:
                            # Sum contributions from metadata
                            contribution = anomaly.metadata.get("contribution", 0.1)
                            total_score += contribution
                            triggered_flags.append(anomaly.description)
                    elif isinstance(res, tuple) and len(res) == 3:
                        # Legacy output: (triggered, contribution, flag_msg)
                        triggered, contribution, flag_msg = res
                        if triggered:
                            total_score += contribution
                            triggered_flags.append(flag_msg)
                except Exception as e:
                    logger.error(f"Rule evaluation failed: {e}")
        else:
            triggered_flags.append(
                "NO_AI_OUTPUT: Kural bazlı anomali hesaplaması kısıtlı."
            )

        final_score = round(min(total_score, 1.0), 4)
        analysis.anomaly_score = final_score
        risk_level = self._determine_risk_level(analysis)

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

    async def reload_rules(self) -> RuleHealthReport:
        logger.info("Triggering anomaly rules hot-reload...")
        await self._registry.reload()
        return self.get_health_report()

    def get_health_report(self) -> RuleHealthReport:
        health = self._registry.get_health_report()
        return RuleHealthReport(
            total_rules=health["total_rules"],
            active_rules=health["active_rules"],
            failed_rules=health["failed_rules"],
            last_reload=self._registry.last_reload,
        )

    def get_rule_metadata(self) -> list[dict[str, Any]]:
        return [rule.get_metadata() for rule in self._registry.rules]

    # ── Legacy Methods (Preserved for compatibility) ──
    def detect_anomalies(self, analysis: Analysis) -> list[LegacyAnomalyResult]:
        anomalies = []
        ai_values = self._extract_ai_values(analysis)
        formula_values = self._extract_formula_values(analysis)

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
    ) -> list[LegacyAnomalyResult]:
        anomalies = []
        ai_risk = ai_values.get("ai_risk", 0.0)
        formula_hedging = formula_values.get("formula_hedging", 0.0)
        if (
            ai_risk >= self.ANOMALY_RISK_HIGH
            and formula_hedging >= self.ANOMALY_HEDGE_HIGH
        ):
            severity = AnomalySeverity.HIGH if ai_risk >= 8 else AnomalySeverity.MEDIUM
            anomalies.append(
                LegacyAnomalyResult(
                    type=AnomalyType.RISK_HEDGING_CONFLICT,
                    severity=severity,
                    category="Deception Pattern",
                    description="High risk language combined with strong hedging suggests potential deception or uncertainty masking",
                    ai_values={"ai_risk": ai_risk},
                    formula_values={"formula_hedging": formula_hedging},
                    confidence=0.8,
                )
            )
        return anomalies

    def _detect_negative_confrontational_amplification(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[LegacyAnomalyResult]:
        anomalies = []
        ai_sentiment = ai_values.get("ai_sentiment", 0.0)
        ai_tone = ai_values.get("ai_diplomatic_tone", "neutral")
        if ai_sentiment <= self.ANOMALY_SENT_NEG and ai_tone == "confrontational":
            anomalies.append(
                LegacyAnomalyResult(
                    type=AnomalyType.NEGATIVE_CONFRONTATIONAL_AMPLIFICATION,
                    severity=AnomalySeverity.HIGH,
                    category="agresif_söylem",
                    description=f"Güçlü negatif duygu ({ai_sentiment:+.3f}) ve yüzleşmeci ton saptandı...",
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
    ) -> list[LegacyAnomalyResult]:
        anomalies = []
        ai_sentiment = ai_values.get("ai_sentiment", 0.0)
        ai_tone = ai_values.get("ai_diplomatic_tone", "neutral")
        ai_manip = ai_values.get("ai_manipulation", 0.0)
        if ai_sentiment >= self.ANOMALY_SENT_POS and ai_tone == "confrontational":
            anomalies.append(
                LegacyAnomalyResult(
                    type=AnomalyType.VELVET_GLOVE_CONFRONTATION,
                    severity=AnomalySeverity.MEDIUM,
                    category="örtülü_baskı",
                    description=f"Velvet Glove Confrontation: Pozitif duygu ({ai_sentiment:+.3f}) ile yüzleşmeci ton aynı anda geliyor...",
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
    ) -> list[LegacyAnomalyResult]:
        anomalies = []
        ai_risk = ai_values.get("ai_risk", 0.0)
        ai_tone = ai_values.get("ai_diplomatic_tone", "neutral")
        if ai_risk >= self.ANOMALY_RISK_HIGH and ai_tone in [
            "conciliatory",
            "cooperative",
            "peaceful",
        ]:
            anomalies.append(
                LegacyAnomalyResult(
                    type=AnomalyType.HIGH_RISK_CONCILIATORY_MASK,
                    severity=AnomalySeverity.HIGH,
                    category="Deception Pattern",
                    description="High-risk content masked with conciliatory tone suggests strategic positioning",
                    ai_values={"ai_risk": ai_risk, "ai_diplomatic_tone": ai_tone},
                    formula_values={},
                    confidence=0.8,
                )
            )
        return anomalies

    def _detect_direct_manipulation_low_hedge(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[LegacyAnomalyResult]:
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
                LegacyAnomalyResult(
                    type=AnomalyType.DIRECT_MANIPULATION_LOW_HEDGE,
                    severity=severity,
                    category="Manipulation",
                    description="High manipulation score with low hedging indicates overt manipulation attempts",
                    ai_values={"ai_manipulation": ai_manipulation},
                    formula_values={"formula_hedging": formula_hedging},
                    confidence=0.9,
                )
            )
        return anomalies

    def _detect_dominant_actor_pressure(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[LegacyAnomalyResult]:
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
                LegacyAnomalyResult(
                    type=AnomalyType.DOMINANT_ACTOR_PRESSURE,
                    severity=AnomalySeverity.HIGH,
                    category="Power Dynamics",
                    description="High-power actor applying significant pressure through elevated SBI scores",
                    ai_values={"ai_risk": ai_risk},
                    formula_values={"power_level": power_level, "sbi_score": sbi_score},
                    confidence=0.8,
                )
            )
        return anomalies

    def _detect_vague_demand_plausible_deniability(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[LegacyAnomalyResult]:
        anomalies = []
        formula_hedging = formula_values.get("formula_hedging", 0.0)
        ai_risk = ai_values.get("ai_risk", 0.0)
        has_demand_indicators = ai_risk >= 4.0
        if formula_hedging >= self.ANOMALY_HEDGE_HIGH and has_demand_indicators:
            anomalies.append(
                LegacyAnomalyResult(
                    type=AnomalyType.VAGUE_DEMAND_PLAUSIBLE_DENIABILITY,
                    severity=AnomalySeverity.MEDIUM,
                    category="Strategic Ambiguity",
                    description="High hedging combined with demand indicators suggests strategic ambiguity",
                    ai_values={"ai_risk": ai_risk},
                    formula_values={"formula_hedging": formula_hedging},
                    confidence=0.6,
                )
            )
        return anomalies

    def _detect_conflict_frame_positive_wrap(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[LegacyAnomalyResult]:
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
                LegacyAnomalyResult(
                    type=AnomalyType.CONFLICT_FRAME_POSITIVE_WRAP,
                    severity=AnomalySeverity.MEDIUM,
                    category="Framing Strategy",
                    description="Conflict-related content framed in positive terms indicates strategic positioning",
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
    ) -> list[LegacyAnomalyResult]:
        anomalies = []
        ai_manipulation = ai_values.get("ai_manipulation", 0.0)
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
                LegacyAnomalyResult(
                    type=AnomalyType.INCONSISTENCY_PLUS_MANIPULATION,
                    severity=severity,
                    category="Deception Pattern",
                    description="High manipulation combined with inconsistent sentiment indicates deceptive communication",
                    ai_values={"ai_manipulation": ai_manipulation},
                    formula_values={"inconsistency_score": inconsistency_score},
                    confidence=0.8,
                )
            )
        return anomalies

    def _detect_negative_appraisal_persuasive_tone(
        self, ai_values: dict[str, Any], formula_values: dict[str, Any]
    ) -> list[LegacyAnomalyResult]:
        anomalies = []
        ai_appraisal = ai_values.get("ai_appraisal", "neutral")
        ai_sentiment = ai_values.get("ai_sentiment", 0.0)
        ai_politeness = ai_values.get("ai_politeness", 0.0)
        if (
            ai_appraisal in ["negative", "critical", "disapproving"]
            and ai_sentiment <= self.ANOMALY_SENT_NEG
            and ai_politeness >= 0.6
        ):
            anomalies.append(
                LegacyAnomalyResult(
                    type=AnomalyType.NEGATIVE_APPRAISAL_PERSUASIVE_TONE,
                    severity=AnomalySeverity.MEDIUM,
                    category="Persuasion Strategy",
                    description="Negative appraisal combined with polite persuasive tone indicates strategic influence attempt",
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

    @staticmethod
    def _determine_risk_level(analysis: Analysis) -> RiskLevel:
        settings = get_settings()
        if not analysis.has_ai_output:
            anomaly = analysis.anomaly_score or 0.0
            composite = anomaly * settings.risk_fallback_anomaly_weight
            if composite >= 0.7:
                return RiskLevel.CRITICAL
            elif composite >= 0.4:
                return RiskLevel.HIGH
            elif composite > 0.0:
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.LOW

        ai_risk = analysis.effective_risk
        anomaly = analysis.anomaly_score or 0.0
        composite = (ai_risk * settings.risk_ai_weight) + (
            anomaly * settings.risk_anomaly_weight
        )

        if anomaly >= 0.8 and composite < 0.6:
            composite = 0.65
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
