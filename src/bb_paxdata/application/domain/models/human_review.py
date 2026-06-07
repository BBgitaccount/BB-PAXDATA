"""
Human Review domain modelleri.

Bu modeller immutable Pydantic yapılarıdır.
AI çıktıları burada referans olarak tutulur, değiştirilmez.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AgreementStatus(str, Enum):
    AGREED = "AGREED"  # Uzman AI ile tamamen uyuştu
    PARTIAL = "PARTIAL"  # Kısmi uyuşma (bazı alanlar farklı)
    DISAGREED = "DISAGREED"  # Tam anlaşmazlık
    ESCALATED = "ESCALATED"  # Uzman "bu vaka daha üst seviyeye gitsin" dedi


class HumanReview(BaseModel):
    """
    Bir uzmanın bir AI analizine verdiği değerlendirme.

    Kural: ai_* alanları ASLA değiştirilmez. Bunlar referans veritir.
    human_* alanları uzmanın düzeltmeleridir.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    analysis_id: str  # FK → ai_sentence_analyses.id
    reviewer_id: str  # örn: "dr_yilmaz_01"
    sentence_text: str | None = None

    # --- AI'ın orijinal çıktıları (salt okunur referans) ---
    ai_sbi_score: float | None = None
    ai_dominant_frame: str | None = None
    ai_risk_level: RiskLevel | None = None
    ai_sentiment_score: float | None = None

    # --- Uzmanın düzeltmeleri ---
    human_sbi_score: float | None = Field(default=None, ge=-100.0, le=100.0)
    human_dominant_frame: str | None = None
    human_risk_level: RiskLevel | None = None
    human_sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)

    # --- Meta ---
    agreement_status: AgreementStatus
    disagreement_reason: str | None = Field(
        default=None,
        max_length=2000,
        description="Uzmanın anlaşmazlık gerekçesi — kalibrasyon için kritik veri",
    )
    review_duration_seconds: int | None = None  # Uzmanın ne kadar süre harcadığı
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_sbi_disagreement(self) -> bool:
        if self.ai_sbi_score is None or self.human_sbi_score is None:
            return False
        return abs(self.ai_sbi_score - self.human_sbi_score) > 5.0  # 5 puan tolerans

    @property
    def sbi_delta(self) -> float | None:
        if self.ai_sbi_score is None or self.human_sbi_score is None:
            return None
        return self.human_sbi_score - self.ai_sbi_score

    @property
    def has_frame_disagreement(self) -> bool:
        return (
            self.ai_dominant_frame is not None
            and self.human_dominant_frame is not None
            and self.ai_dominant_frame != self.human_dominant_frame
        )

    @property
    def has_risk_disagreement(self) -> bool:
        return (
            self.ai_risk_level is not None
            and self.human_risk_level is not None
            and self.ai_risk_level != self.human_risk_level
        )
