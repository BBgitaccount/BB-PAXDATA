from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

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


class Analysis(BaseModel):
    """Represents analysis results for a segment or sentence with various assessments.

    Includes risk, sentiment, and anomaly assessments.
    Pipeline boyunca her aşamada model_copy(update=...) ile zenginleştirilir.
    Hiçbir zaman doğrudan mutate edilmez (immutable data flow).
    """

    # ── Temel Alanlar ──────────────────────────────────────────────
    id: str = Field(
        default_factory=lambda: f"anal-{uuid.uuid4().hex[:8]}",
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

    # ── Geleneksel NLP Çıktıları ───────────────────────────────────
    entities: list[dict[str, Any]] = Field(
        default_factory=list, description="NER ile çıkarılan varlıklar"
    )
    tokens: list[str] = Field(default_factory=list, description="Tokenizer çıktısı")
    sentences: list[str] = Field(
        default_factory=list, description="Cümle segmentasyonu"
    )
    sentence_count: int = Field(default=0, description="Cümle sayısı")

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
        description="Prompt şablonunun SHA256 hash'i (ilk 16 karakter) — audit için",
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
        default=None, ge=0.0, le=1.0, description="Manipulation likelihood score"
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

    # ── None-Safety Hesaplama Property'leri ───────────────────────

    @property
    def has_ai_output(self) -> bool:
        """AI çıktısının gerçekten mevcut olup olmadığını döner.
        Anomali servisi bu property'yi kontrol etmeli — sahte anomali üretimi engellenir.
        """
        return self.ai_sentiment_score is not None or self.ai_risk_score is not None

    @property
    def effective_sentiment(self) -> float:
        """AI sentiment skoru varsa onu, yoksa nötr (0.0) döner.
        Tüketici kodlar getattr KULLANMAMALI — bu property yeterli."""
        return self.ai_sentiment_score if self.ai_sentiment_score is not None else 0.0

    @property
    def effective_risk(self) -> float:
        """AI risk skoru varsa onu, yoksa 0.0 döner."""
        return self.ai_risk_score if self.ai_risk_score is not None else 0.0


# Alias for compatibility with instructions
SentenceAnalysis = Analysis


class SegmentInsight(BaseModel):
    # [FAZ3] PromptRegistry entegrasyonu
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )


class DemandAnalysis(BaseModel):
    # [FAZ3] PromptRegistry entegrasyonu
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )


class PanelSynthesis(BaseModel):
    # [FAZ3] PromptRegistry entegrasyonu
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )


class FailCheckAnalysis(BaseModel):
    # [FAZ3] PromptRegistry entegrasyonu
    prompt_version: str | None = Field(
        default=None,
        description="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
    )
