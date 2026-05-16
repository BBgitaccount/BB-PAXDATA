from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult
    from bb_paxdata.domain.models.analysis import Analysis


@dataclass
class PipelineResult:
    """
    Pipeline çıktı zarfı.
    Hem nihai Analysis modelini hem ham servis verilerini taşır.
    Ham veriler debug ve audit amacıyla korunur.
    """

    analysis: Analysis
    raw_ner: dict[str, Any] = field(default_factory=dict)
    raw_tokenizer: dict[str, Any] = field(default_factory=dict)
    raw_ai: AIAnalysisResult | None = None
    contradiction_score: float | None = None
    success: bool = True
    errors: list[str] = field(default_factory=list)
    stage: str = "completed"  # Hata durumunda hangi aşamada kaldığı
