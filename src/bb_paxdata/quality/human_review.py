from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from bb_paxdata.domain.enums.metric_type import MetricType
from bb_paxdata.domain.enums.priority import Priority
from bb_paxdata.domain.enums.review_status import ReviewStatus
from bb_paxdata.domain.enums.review_type import ReviewType

if TYPE_CHECKING:
    pass


class MetricOverride(BaseModel):
    """İnsan tarafından düzeltilen metrik değeri."""

    model_config = ConfigDict(frozen=True)

    original_value: float | None = Field(
        None, description="AI tarafından üretilen orijinal değer"
    )
    overridden_value: float | None = Field(
        None, description="İnsan tarafından düzeltilen değer"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="İncelemecinin güven skoru"
    )
    justification: str | None = Field(None, description="Düzeltme gerekçesi")


class HumanReviewRequest(BaseModel):
    """İnsan doğrulama (HITL) talebi.

    Reference:
        - Grimmer & Stewart (2013) - İlke 2: İnsan doğrulaması zorunludur.
    """

    model_config = ConfigDict(frozen=True)

    analysis_id: UUID
    segment_indices: list[int] | None = Field(
        None, description="İnceleme istenen segmentler"
    )
    review_type: ReviewType
    priority: Priority
    requested_metrics: list[MetricType] | None = Field(
        None, description="İnceleme istenen metrikler"
    )
    academic_justification: str | None = Field(
        None, description="Grimmer & Stewart ilkesine referans"
    )
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_by: str = Field(..., description="Sistem veya kullanıcı kimliği")


class HumanReviewResult(BaseModel):
    """İnsan doğrulama sonucu."""

    model_config = ConfigDict(frozen=True)

    review_id: UUID
    analysis_id: UUID
    reviewer_id: str
    status: ReviewStatus
    metric_overrides: dict[MetricType, MetricOverride]
    reviewer_notes: str | None = None
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    audit_hash: str = Field(..., description="SHA256 hash of the review record")


class HumanReviewService(Protocol):
    """İnsan doğrulama servisi arayüzü.

    Somut implementasyonlar infrastructure katmanında tanımlanacaktır.
    """

    async def submit_request(self, request: HumanReviewRequest) -> UUID:
        """Yeni bir inceleme talebi gönderir."""
        ...

    async def get_pending_reviews(
        self, priority: Priority | None = None
    ) -> list[HumanReviewRequest]:
        """Bekleyen inceleme taleplerini listeler."""
        ...

    async def submit_result(self, result: HumanReviewResult) -> None:
        """İnceleme sonucunu kaydeder."""
        ...

    async def get_review_history(self, analysis_id: UUID) -> list[HumanReviewResult]:
        """Bir analize ait inceleme geçmişini döndürür."""
        ...
