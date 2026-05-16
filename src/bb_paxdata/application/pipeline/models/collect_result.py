# src/bb_paxdata/application/pipeline/models/collect_result.py
"""
COLLECT aşamasından çıkan ara veri modeli.
CountryReferenceCollector'ın ürettiği entity'leri taşır.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from bb_paxdata.domain.models.ai_analysis import AIAnalysisResult
from bb_paxdata.domain.models.country_reference import CountryReference
from bb_paxdata.domain.models.dki import LLMPositionEstimate, SemanticShiftResult
from bb_paxdata.domain.models.frame_annotation import (
    CueMatch,
    FrameDetectionResult,
    FrameSalienceResult,
)
from bb_paxdata.domain.models.negation_cue import NegationCue
from bb_paxdata.domain.models.power_index import PowerIndex
from bb_paxdata.domain.models.risk_signal import RiskSignal
from bb_paxdata.domain.models.topic import TopicResult
from pydantic import BaseModel, ConfigDict, Field


class CountryCollectResult(BaseModel):
    """
    COLLECT aşamasının country-extraction çıktısı.
    Immutable taşıyıcıdır; persistence bu aşamada yapılmaz.
    """

    model_config = ConfigDict(frozen=True)

    panel_id: str
    references: tuple[CountryReference, ...] = Field(default_factory=tuple)
    collector_version: str = Field(default="country_ner@v1.0")
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    error: str | None = Field(default=None)

    @property
    def succeeded(self) -> bool:
        return self.error is None and len(self.references) > 0


class CollectResult(BaseModel):
    """
    COLLECT aşamasının tüm servis çıktılarının birleşimi.
    """

    model_config = ConfigDict(frozen=True)

    raw_ner: dict[str, Any] = Field(default_factory=dict)
    raw_tokenizer: dict[str, Any] = Field(default_factory=dict)
    raw_ai: AIAnalysisResult | None = None
    country_references: tuple[CountryReference, ...] = Field(default_factory=tuple)
    negation_cues: Sequence[NegationCue] = Field(default_factory=tuple)
    risk_signals: Sequence[RiskSignal] = Field(default_factory=tuple)
    power_indices: dict[str, PowerIndex] = Field(
        default_factory=dict, description="Speaker ID -> PowerIndex"
    )
    topic_result: TopicResult | None = None
    frame_detection: FrameDetectionResult | None = None
    frame_cues: list[CueMatch] = Field(default_factory=list)
    frame_salience: FrameSalienceResult | None = None

    # Phase 7 SBI Components
    stance_density: float | None = None
    engagement_score: float | None = None

    # Phase 8 DKI Components
    llm_position: LLMPositionEstimate | None = None
    semantic_shift: SemanticShiftResult | None = None

    errors: list[str] = Field(default_factory=list)
