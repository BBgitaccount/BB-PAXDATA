# ============================================================
# DOSYA: src/bb_paxdata/domain/services/protocols.py
# AÇIKLAMA: Servis arayüzleri — structural typing (Protocol)
# ============================================================

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..enums import RiskLevel
from ..models.ai_analysis import AIAnalysisResult
from ..models.analysis import Analysis
from ..models.dki import (
    DynamicPositionResult,
    LLMPositionEstimate,
    PositionCalibration,
    SegmentWindow,
    SemanticShiftResult,
    SpeakerTrajectory,
)


@dataclass(frozen=True)
@runtime_checkable
class SemanticShiftCalculator(Protocol):
    async def calculate_shift(
        self,
        current: SegmentWindow,
        historical: list[SegmentWindow],
        idf_reference: dict[str, float] | None = None,
    ) -> SemanticShiftResult:
        """Compute semantic shift between discourse contexts (Azarbonyad 2017)."""
        ...


@runtime_checkable
class DynamicPositionTracker(Protocol):
    async def compute_velocity(
        self,
        trajectory: SpeakerTrajectory,
        smoothing_window: int = 3,
    ) -> DynamicPositionResult:
        """Compute Δθ/Δt and acceleration for speaker position time-series."""
        ...


@runtime_checkable
class LLMPositionEstimator(Protocol):
    async def estimate_position(
        self,
        text: str,
        policy_dimension: str,
        schema_enforce: bool = True,
    ) -> LLMPositionEstimate:
        """Deterministic LLM-based position estimation (Cambridge Core 2026)."""
        ...

    async def calibrate_against_wordfish(
        self,
        llm_estimates: list[LLMPositionEstimate],
        wordfish_thetas: list[float],
    ) -> PositionCalibration:
        """Compute calibration drift between LLM and Wordfish positions."""
        ...


@dataclass(frozen=True)
class AnomalyResult:
    """CrossAnomalyService.detect() metodunun dönüş tipi."""

    score: float  # [0.0, 1.0]
    flags: list[str]  # Tetiklenen kural mesajları
    risk_level: RiskLevel
    triggered_count: int = 0


@runtime_checkable
class NERServiceProtocol(Protocol):
    async def extract(self, text: str, language: str | None = None) -> dict[str, Any]:
        """{"entities": [...], "language": str} döner."""
        ...


@runtime_checkable
class TokenizerProtocol(Protocol):
    async def tokenize(self, text: str, language: str | None = None) -> dict[str, Any]:
        """{"tokens": [...], "sentences": [...], "sentence_count": int, "language": str} döner."""
        ...


@runtime_checkable
class AIAnalystProtocol(Protocol):
    async def analyze(
        self,
        text: str,
        prompt_id: str | None = None,
        forced_version: str | None = None,
        language: str | None = None,
    ) -> AIAnalysisResult: ...


@runtime_checkable
class AnomalyServiceProtocol(Protocol):
    async def detect(self, analysis: Analysis) -> AnomalyResult: ...
