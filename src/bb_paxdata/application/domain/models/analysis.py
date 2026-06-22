from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator

from bb_paxdata.application.domain.utils.json_validation import validate_json_safe

from ..enums import (
    AnomalySeverity,
    AnomalyType,
    EvidenceType,
    FailCategory,
    FutureRiskTier,
    RiskLevel,
    RiskTrajectory,
    ValidationCheckType,
)
from .appraisal_vector import AppraisalVector
from .argument import ArgumentGraph
from .base import AggregateRoot
from .bilateral_sentiment import BilateralSentiment
from .discourse_network import DiscourseFlow
from .dki import DKIResult
from .frame_annotation import FrameDetectionResult, FrameSalienceResult
from .negation_cue import NegationCue
from .power_index import PowerIndex
from .presupposition import Presupposition
from .risk_signal import RiskSignal
from .sbi_models import SBIResult
from .segment import Segment
from .service_results import HedgingResult
from .speech_act import SpeechActClassification
from .topic_synthesis import TopicSynthesis


class Analysis(AggregateRoot):
    """Represents analysis results for a segment or sentence with various assessments.

    Includes risk, sentiment, and anomaly assessments.
    Pipeline boyunca her aşamada model_copy(update=...) ile zenginleştirilir.
    Hiçbir zaman doğrudan mutate edilmez (immutable data flow).
    """

    # ── Temel Alanlar ──────────────────────────────────────────────
    id: str = Field(
        default_factory=lambda: f"anal-{uuid.uuid4().hex}",
        description="Unique identifier for the analysis",
    )
    source_text: str = Field(default="", description="Analiz edilen orijinal metin")
    language: str = Field(
        default="unknown", description="Tespit edilen dil (tr/en/mixed)"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC analiz zaman damgası (ISO 8601)",
    )

    segment_id: str | None = Field(default=None, description="ID of analyzed segment")
    sentence_id: str | None = Field(default=None, description="ID of analyzed sentence")
    sentence_code: str | None = Field(
        default=None, description="Unique short code for the sentence"
    )
    speaker_id: str | None = Field(
        default=None, description="ID of the speaker analyzed"
    )

    # Risk assessment
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW, description="Current risk level"
    )
    risk_trajectory: RiskTrajectory | None = Field(
        default=None, description="Risk trajectory trend"
    )
    future_risk_tier: FutureRiskTier | None = Field(
        default=None, description="Projected future risk tier"
    )

    # Sentiment and emotional metrics
    sentiment_score: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Sentiment score from -1 to 1"
    )
    emotional_intensity: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Emotional intensity score"
    )
    stress_level: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Stress level indicator"
    )

    # LIWC2015 proxy scores (Faz 7 integration)
    liwc_clout: float | None = Field(
        None, ge=0.0, le=1.0, description="LIWC clout score"
    )
    liwc_analytic: float | None = Field(
        None, ge=0.0, le=1.0, description="LIWC analytic score"
    )
    liwc_authenticity: float | None = Field(
        None, ge=0.0, le=1.0, description="LIWC authenticity score"
    )
    liwc_tone: float | None = Field(
        None, ge=-1.0, le=1.0, description="LIWC tone score"
    )

    # ── Geleneksel NLP Çıktıları ───────────────────────────────────
    entities: list[dict[str, Any]] = Field(
        default_factory=list, description="NER ile çıkarılan varlıklar"
    )
    tokens: list[str] = Field(default_factory=list, description="Tokenizer çıktısı")
    sentences: list[str] = Field(
        default_factory=list, description="Cümle segmentasyonu"
    )
    negation_cues: Sequence[NegationCue] = Field(
        default_factory=tuple, description="Negation cues for the analysis"
    )
    risk_signals: Sequence[RiskSignal] = Field(
        default_factory=tuple, description="Risk signals for the analysis"
    )
    power_indices: dict[str, PowerIndex] = Field(
        default_factory=dict, description="Speaker ID -> PowerIndex"
    )
    segments: list[Segment] = Field(
        default_factory=list, description="Panel/sentence segments for network assembly"
    )

    # ── AI Üretilmiş Çıktılar (KRİTİK: Tüm alanlar Optional) ──────
    ai_sentiment_score: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Duygu analizi skoru (-1 negatif, +1 pozitif)",
    )
    ai_risk_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Diplomatik risk skoru (0 güvenli, 1 yüksek risk)",
    )
    ai_sentiment_label: str | None = Field(
        default=None, description="Duygu etiketi: positive / negative / neutral / mixed"
    )
    ai_risk_factors: list[str] = Field(
        default_factory=list,
        description="AI tarafından tespit edilen risk faktörü listesi",
    )
    ai_summary: str | None = Field(
        default=None, description="AI tarafından üretilen özet cümle"
    )
    ai_key_claims: list[str] = Field(
        default_factory=list, description="AI tarafından çıkarılan ana iddialar"
    )

    # ── Prompt İzlenebilirlik (Audit Trail) ───────────────────────
    prompt_version: str | None = Field(
        default=None,
        description="prompt_id@version formatı, ör: 'diplomatic_analysis@v2.1'",
    )
    prompt_hash: str | None = Field(
        default=None,
        description="Prompt şablonunun SHA256 hash'i (tam 64 karakter) — audit için",
    )
    model_name: str | None = Field(
        default=None,
        description="Kullanılan AI modelinin adı (gpt-4o, claude-3.5-sonnet, vb.)",
    )

    # Anomaly detection
    anomalies: list[AnomalySeverity] = Field(
        default_factory=list, description="List of detected anomaly severities"
    )
    anomaly_types: list[AnomalyType] = Field(
        default_factory=list, description="Types of anomalies detected"
    )
    anomaly_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence in anomaly detection"
    )
    anomaly_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="CrossAnomalyService tarafından hesaplanan bileşik anomali skoru",
    )
    anomaly_flags: list[str] = Field(
        default_factory=list,
        description="Tetiklenen anomali kurallarının mesaj listesi",
    )

    # Validation results
    validation_checks: dict[ValidationCheckType, bool] = Field(
        default_factory=dict, description="Validation check results"
    )
    validation_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Overall validation score"
    )
    fail_category: FailCategory | None = Field(
        default=None, description="Category of validation failures"
    )

    # Evidence and confidence
    evidence_types: list[EvidenceType] = Field(
        default_factory=list, description="Types of evidence found"
    )
    evidence_strength: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Strength of evidence"
    )
    confidence_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Overall confidence score"
    )

    # Additional metrics
    complexity_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Complexity score"
    )
    coherence_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Coherence score"
    )
    manipulation_score: float | None = Field(
        default=None, le=1.0, description="Manipulation likelihood score"
    )

    # Analysis metadata
    analysis_version: str = Field(
        default="1.0", description="Version of analysis methodology"
    )
    analysis_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When analysis was performed",
    )
    analyzer_id: str | None = Field(
        default=None, description="ID of analyzer system or analyst"
    )

    # Notes and explanations
    sumcomplexity_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Complexity score"
    )
    detailed_findings: str | None = Field(
        default=None, description="Detailed analysis findings"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommended actions based on analysis"
    )

    # Phase 5 Topic Modeling
    topic_node_mapping: dict[str, list[str]] = Field(
        default_factory=dict, description="BERTopic topic_id -> list of DNA node_ids"
    )
    topic_synthesis: TopicSynthesis | None = Field(
        default=None, description="Probabilistic topic modeling results (Faz 5)"
    )
    topic_diversity_score: float | None = Field(
        default=None,
        description=(
            "Shannon entropy of BERTopic P(topic|doc) distribution. "
            "Derived from TopicSynthesis.topic_diversity after assembly. "
            "0.0 = single-topic focused discourse; higher = dispersed topics."
        ),
    )
    discourse_flow: DiscourseFlow | None = Field(
        default=None, description="DNA network flow (Faz 4)"
    )
    bilateral_metrics: list[BilateralSentiment] = Field(
        default_factory=list, description="Bilateral relationship metrics (Faz 4)"
    )

    # Phase 6 Computational Framing
    framing: str | None = Field(default=None, description="Dominant framing category")
    frame_detection: FrameDetectionResult | None = Field(
        default=None, description="Hamborg (2023) PFA pipeline results"
    )
    frame_salience: FrameSalienceResult | None = Field(
        default=None, description="Entman (1993) frame salience results"
    )

    # Phase 7 Speaker-Based Index
    sbi_result: SBIResult | None = Field(
        default=None, description="Composite Speaker-Based Index results (Faz 7)"
    )

    # Phase 8 Discourse-Kinetic Index
    dki_result: DKIResult | None = Field(
        default=None, description="Discourse-Kinetic Index results (Faz 8)"
    )

    # Phase 2 Dual-Gate Consensus
    consensus_result: Any | None = Field(
        default=None, description="DualGateConsensusLayer sonucu"
    )
    speech_act: SpeechActClassification | None = Field(
        default=None, description="Speech act classification"
    )
    hedging_result: HedgingResult | None = Field(
        default=None, description="Hedging analysis result"
    )
    appraisal_vector: AppraisalVector | None = Field(
        default=None, description="Appraisal theory vector analysis"
    )

    # === Consolidating rich analysis fields from DTO ===
    argument_graph: ArgumentGraph | None = Field(
        default=None,
        description="Peldszus & Stede (2013) argumentation structure graph",
    )
    argument_quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall argumentation quality metric (coherence, coverage)",
    )
    key_claims_extracted: list[str] = Field(
        default_factory=list, description="Top-N most important claims identified"
    )
    controversy_level: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Discourse controversy indicator (0=consensus, 1=highly contested)",
    )
    appraisal_judgment_sanction_count: int = Field(
        default=0, ge=0, description="Total negative social sanction judgments"
    )
    dominant_appraisal_axis: str | None = Field(
        default=None,
        description="Dominant appraisal axis (AFFECT, JUDGMENT, APPRECIATION)",
    )
    hidden_commitments: list[Presupposition] = Field(
        default_factory=list,
        description=(
            "Presuppositions extracted per Lewis (1979) / Beaver & Geurts (2014). "
            "Populated by PresuppositionService post-TASK-A01 SRL enrichment."
        ),
    )

    # ── None-Safety Hesaplama Property'leri ───────────────────────

    @property
    def has_ai_output(self) -> bool:
        """AI çıktısının gerçekten mevcut olup olmadığını döner.
        Anomali servisi bu property'yi kontrol etmeli — sahte anomali üretimi engellenir.
        """
        return any(
            [
                self.ai_sentiment_score is not None,
                self.ai_risk_score is not None,
                self.ai_sentiment_label is not None,
                bool(self.ai_risk_factors),
                self.ai_summary is not None,
                bool(self.ai_key_claims),
            ]
        )

    @property
    def effective_sentiment(self) -> float:
        """AI sentiment skoru varsa onu, yoksa nötr (0.0) döner.
        Tüketici kodlar getattr KULLANMAMALI — bu property yeterli."""
        return self.ai_sentiment_score if self.ai_sentiment_score is not None else 0.0

    @property
    def effective_risk(self) -> float:
        """AI risk skoru varsa onu, yoksa 0.0 döner."""
        return self.ai_risk_score if self.ai_risk_score is not None else 0.0

    @property
    def escalated_risk_score(self) -> float:
        """Zagare (2004) escalation multiplier'lı risk skoru."""
        base_risk = self.effective_risk
        if not self.risk_signals:
            return base_risk

        max_multiplier = max(s.escalation_multiplier for s in self.risk_signals)
        weighted_sum = sum(s.weighted_risk_contribution for s in self.risk_signals)

        return (base_risk * max_multiplier) + (weighted_sum * 0.1)

    @computed_field
    @property
    def hidden_commitment_count(self) -> int:
        return len(self.hidden_commitments)

    @computed_field
    @property
    def commitment_by_type(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for p in self.hidden_commitments:
            result[p.trigger_type.value] = result.get(p.trigger_type.value, 0) + 1
        return result

    @property
    def appraisal_attitude_from_vector(self) -> str:
        """
        Bridge: derive legacy AppraisalAttitude string from AppraisalVector.
        Supersedes ai_appraisal_attitude for downstream rules.
        Returns: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'
        """
        if self.appraisal_vector is None or not self.appraisal_vector.has_any_detection:
            val = getattr(self, "ai_appraisal_attitude", "NEUTRAL") or "NEUTRAL"
            return str(val).upper()
        v = self.appraisal_vector
        dominant_score = max(
            v.affect_score * v.affect_confidence,
            v.judgment_score * v.judgment_confidence,
            v.appreciation_score * v.appreciation_confidence,
            key=abs,
        )
        if dominant_score > 0.15:
            return "POSITIVE"
        if dominant_score < -0.15:
            return "NEGATIVE"
        return "NEUTRAL"

    @property
    def has_argument_analysis(self) -> bool:
        """Check if argument graph analysis completed."""
        return self.argument_graph is not None and len(self.argument_graph.nodes) > 0

    def get_summary_arguments(self, top_n: int = 5) -> list[dict]:
        """Extract top-N most significant arguments for reporting."""
        # Assign to local variable so type checkers know
        # argument_graph cannot be None past this point.
        graph = self.argument_graph
        if graph is None or len(graph.nodes) == 0:
            return []

        # Sort by confidence × depth weight
        scored_nodes = [
            {
                "segment_id": node.segment_id,
                "text": node.text[:200],
                "type": node.node_type.value,
                "speaker": node.speaker,
                "confidence": node.confidence,
                "significance": node.confidence * (1 + node.depth * 0.1),
            }
            for node in graph.nodes
        ]

        scored_nodes.sort(key=lambda x: x["significance"], reverse=True)
        return scored_nodes[:top_n]

    def evaluate_high_risk_anomaly(self) -> tuple[bool, float, str]:
        """Evaluate if the risk exceeds the critical threshold (HighRiskThresholdRule)."""
        CRITICAL_THRESHOLD = 0.8
        if not self.has_ai_output:
            return False, 0.0, ""

        risk = self.effective_risk
        if risk >= CRITICAL_THRESHOLD:
            return (
                True,
                risk * 0.6,
                f"HIGH_RISK_THRESHOLD: risk={risk:.2f} >= {CRITICAL_THRESHOLD}",
            )
        return False, 0.0, ""

    def evaluate_negative_sentiment_anomaly(self) -> tuple[bool, float, str]:
        """Evaluate if the sentiment indicates extreme negativity (NegativeSentimentRule)."""
        NEGATIVE_THRESHOLD = -0.7
        if not self.has_ai_output:
            return False, 0.0, ""

        sentiment = self.effective_sentiment
        if sentiment <= NEGATIVE_THRESHOLD:
            score = abs(sentiment) * 0.3
            return (
                True,
                min(score, 0.3),
                f"EXTREME_NEGATIVE_SENTIMENT: sentiment={sentiment:.2f}",
            )
        return False, 0.0, ""

    def evaluate_power_asymmetry_anomaly(self) -> tuple[bool, float, str]:
        """Evaluate if there is significant power asymmetry with negative sentiment."""
        THRESHOLD_ASYMMETRY = 0.5
        THRESHOLD_DELTA = -0.3

        if len(self.power_indices) < 2:
            return False, 0.0, ""

        indices = list(self.power_indices.values())
        idx_a = indices[0].total_power_index
        idx_b = indices[1].total_power_index

        raw_diff = abs(idx_a - idx_b)
        max_idx = max(idx_a, idx_b)
        asymmetry = (raw_diff / max_idx) if max_idx > 0 else 0.0
        sentiment = self.effective_sentiment

        if asymmetry > THRESHOLD_ASYMMETRY and sentiment < THRESHOLD_DELTA:
            return (
                True,
                asymmetry * 0.5,
                f"POWER_ASYMMETRY_ANOMALY: asymmetry={asymmetry:.2f}, sentiment={sentiment:.2f}",
            )

        return False, 0.0, ""

    def evaluate_cheap_talk_anomaly(self) -> tuple[bool, float, str]:
        """Evaluate cheap talk anomaly based on risk signals credibility and power."""
        THRESHOLD_POWER = 0.1
        THRESHOLD_CREDIBILITY = 0.4

        if not self.risk_signals:
            return False, 0.0, ""

        power = 1.0
        if self.speaker_id in self.power_indices:
            power = self.power_indices[self.speaker_id].total_power_index

        max_multiplier = max(s.escalation_multiplier for s in self.risk_signals)
        weighted_score = power * max_multiplier

        # Check for costly signaling or red line
        costly_count = sum(
            1
            for s in self.risk_signals
            if s.signal_type in ("costly_signal", "red_line")
            or (
                hasattr(s.signal_type, "value")
                and s.signal_type.value in ("costly_signal", "red_line")
            )
        )
        credibility = costly_count / len(self.risk_signals)

        if weighted_score > THRESHOLD_POWER and credibility < THRESHOLD_CREDIBILITY:
            return (
                True,
                0.4,
                f"PLAY_TALK_ANOMALY: weighted_score={weighted_score:.2f}, credibility={credibility:.2f}",
            )

        return False, 0.0, ""

    def evaluate_topic_diversity_anomaly(self) -> tuple[bool, float, str]:
        """Evaluate discourse fragmentation anomaly via BERTopic topic distribution entropy."""
        DIVERSITY_THRESHOLD = 2.0
        RISK_AMPLIFIER = 0.35

        if not self.has_ai_output:
            return False, 0.0, ""

        ts = self.topic_synthesis
        if ts is None:
            return False, 0.0, ""

        diversity = ts.topic_diversity
        if diversity <= DIVERSITY_THRESHOLD:
            return False, 0.0, ""

        risk = self.effective_risk
        score = min(
            1.0,
            (diversity / (DIVERSITY_THRESHOLD * 2)) * RISK_AMPLIFIER * (1 + risk),
        )

        return (
            True,
            round(score, 4),
            f"TOPIC_DIVERSITY_ANOMALY: Shannon_H={diversity:.3f} bits "
            f"> threshold={DIVERSITY_THRESHOLD}, risk={risk:.2f}",
        )

    @model_validator(mode="after")
    def validate_json_fields(self) -> Analysis:
        """Ensure entities contains only JSON-safe types."""
        try:
            validate_json_safe(self.entities)
        except TypeError as e:
            raise ValueError(f"Invalid entities: {e}")
        return self


# Alias for compatibility with instructions
SentenceAnalysis = Analysis


class SegmentInsight(BaseModel):
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )


class DemandAnalysis(BaseModel):
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )


class PanelSynthesis(BaseModel):
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )


class FailCheckAnalysis(BaseModel):
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )
