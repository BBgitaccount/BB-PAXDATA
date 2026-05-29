# ============================================================
# DOSYA: src/bb_paxdata/domain/services/cross_anomaly_service.py
# AÇIKLAMA: Kural tabanlı plugin mimarisi — getattr YOK
# ============================================================

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from bb_paxdata.config.settings import get_settings

from ...application.protocols import AnomalyResult as LegacyAnomalyResult
from ..enums import AnomalySeverity, AnomalyType, NegationType, RiskLevel
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


class ToneDriftRule:
    """
    ID: RULE_TONE_DRIFT
    Mantık: Tek segment içinde ardışık cümlelerin sentiment skorlarının varyansı
           popülasyonun 2 standart sapması (2σ) üzerine çıkarsa anomali.
    """

    def __init__(self, sigma_multiplier: float = 2.0, min_sentences: int = 3):
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        self._vader = SentimentIntensityAnalyzer()
        self.sigma_multiplier = sigma_multiplier
        self.min_sentences = min_sentences

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
        sentences = analysis.sentences
        if not sentences or len(sentences) < self.min_sentences:
            return False, 0.0, ""

        # Her cümle için polarity (VADER compound) hesapla
        scores = [self._vader.polarity_scores(s)["compound"] for s in sentences]

        # Ortalama ve Standart Sapma
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
            # Normalize confidence (max_z=4.0)
            confidence = min(1.0, z / 4.0)
            return (
                True,
                round(confidence, 4),
                f"TONE_DRIFT: deviation={max_deviation:.2f} > threshold={threshold:.2f} ({self.sigma_multiplier}σ)",
            )

        return False, 0.0, ""


class EntityFlipRule:
    """
    ID: RULE_ENTITY_FLIP
    Mantık: Aynı entity (GPE veya PERSON) tek segment/cümle grubu içindeki cümlelerde
            taban tabana zıt duygu skorları alıyorsa anomali.
    """

    def __init__(self, flip_threshold: float = 1.0):
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        self._vader = SentimentIntensityAnalyzer()
        self.flip_threshold = flip_threshold
        self.entity_types = {"GPE", "PERSON"}

    def evaluate(self, analysis: Analysis) -> tuple[bool, float, str]:
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


class CrossAnomalyService:
    """
    Tüm anomali kurallarını koordine eden servis.
    Plugin mimarisi: rules listesine yeni kural sınıfı eklemek yeterli.
    IMMUTABLE: Analysis nesnesini mutate etmez; AnomalyResult döner.
    """

    # Anomaly detection thresholds (from AIanalyst_v5_8.py)
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

    def __init__(self, rules: list[AnomalyRule] | None = None):
        self.rules: list[AnomalyRule] = rules or [
            SentimentRiskDivergenceRule(),
            HighRiskThresholdRule(),
            NegativeSentimentRule(),
            PowerAsymmetryAnomalyRule(),
            CheapTalkAnomalyRule(),
            ToneDriftRule(),
            EntityFlipRule(),
        ]
        self.confidence = 1.0

    def analyze(self, analysis: Analysis, **kwargs: Any) -> Any:
        """Detect cross-anomalies in analysis results.

        Args:
            analysis: The analysis results to check for anomalies
            **kwargs: Additional analysis parameters

        Returns:
            List of detected anomalies
        """
        return self.detect_anomalies(analysis)

    def detect_anomalies(self, analysis: Analysis) -> list[LegacyAnomalyResult]:
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
        """Extract AI-derived values from analysis."""
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
        """Extract formula-derived values from analysis."""
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
        """Detect risk-hedging conflict anomalies."""
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
    ) -> list[LegacyAnomalyResult]:
        """Detect negative confrontational amplification anomalies."""
        anomalies = []
        ai_sentiment = ai_values.get("ai_sentiment", 0.0)
        ai_tone = ai_values.get("ai_diplomatic_tone", "neutral")

        if ai_sentiment <= self.ANOMALY_SENT_NEG and ai_tone == "confrontational":
            anomalies.append(
                LegacyAnomalyResult(
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
    ) -> list[LegacyAnomalyResult]:
        """Detect velvet glove confrontation anomalies."""
        anomalies = []
        ai_sentiment = ai_values.get("ai_sentiment", 0.0)
        ai_tone = ai_values.get("ai_diplomatic_tone", "neutral")
        ai_manip = ai_values.get("ai_manipulation", 0.0)

        if ai_sentiment >= self.ANOMALY_SENT_POS and ai_tone == "confrontational":
            manip_note = "güçlendiriyor" if ai_manip >= 0.4 else "henüz desteklemiyor"
            anomalies.append(
                LegacyAnomalyResult(
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
    ) -> list[LegacyAnomalyResult]:
        """Detect high risk conciliatory mask anomalies."""
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
    ) -> list[LegacyAnomalyResult]:
        """Detect direct manipulation with low hedging."""
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
    ) -> list[LegacyAnomalyResult]:
        """Detect dominant actor pressure anomalies."""
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
    ) -> list[LegacyAnomalyResult]:
        """Detect vague demands with plausible deniability."""
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
    ) -> list[LegacyAnomalyResult]:
        """Detect conflict frame with positive wrapping."""
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
    ) -> list[LegacyAnomalyResult]:
        """Detect inconsistency combined with manipulation."""
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
    ) -> list[LegacyAnomalyResult]:
        """Detect negative appraisal with persuasive tone."""
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
        settings = get_settings()
        # 1. Durum: AI verisi yoksa (AI çökmüş veya atlanmışsa)
        if not analysis.has_ai_output:
            anomaly = analysis.anomaly_score or 0.0
            # AI yokken anomali skoru tam ağırlıkla hesaba katılır
            composite = anomaly * settings.risk_fallback_anomaly_weight

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

        composite = (ai_risk * settings.risk_ai_weight) + (
            anomaly * settings.risk_anomaly_weight
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
