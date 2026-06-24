"""
Kalibrasyon raporu domain modeli.

AI versiyonu bazında inter-rater agreement istatistiklerini tutar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class CalibrationReport(BaseModel):
    """
    Bir prompt versiyonu için hesaplanan kalibrasyon istatistikleri.
    Periyodik olarak (örn: haftalık) hesaplanır ve DB'ye yazılır.
    """

    model_config = ConfigDict(frozen=False)

    id: str = Field(default_factory=lambda: str(uuid4()))
    prompt_version: str  # örn: "sentence_analysis@v1.2"
    evaluation_period_start: datetime
    evaluation_period_end: datetime

    # Inter-rater agreement
    cohens_kappa_frame: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Frame sınıflandırması için Cohen's Kappa (>0.67 güvenilir)",
    )
    cohens_kappa_risk: float | None = Field(
        default=None, ge=-1.0, le=1.0, description="Risk seviyesi için Cohen's Kappa"
    )

    # AI vs Human agreement
    ai_human_f1_frame: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_human_f1_risk: float | None = Field(default=None, ge=0.0, le=1.0)
    sbi_mae: float | None = None  # Mean Absolute Error: AI SBI vs Human SBI

    # İstatistik özeti
    total_reviews: int = 0
    total_disagreements: int = 0
    top_disagreement_patterns: list[str] = Field(default_factory=list)

    # Aksiyon önerisi
    requires_prompt_update: bool = False
    requires_weight_update: bool = False
    alert_message: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def disagreement_rate(self) -> float:
        if self.total_reviews == 0:
            return 0.0
        return self.total_disagreements / self.total_reviews

    @property
    def is_reliable(self) -> bool:
        """Kappa > 0.67 ise veri güvenilirdir (Landis & Koch, 1977)."""
        kappas = [
            k
            for k in [self.cohens_kappa_frame, self.cohens_kappa_risk]
            if k is not None
        ]
        if not kappas:
            return False
        return all(k > 0.67 for k in kappas)
