# src/bb_paxdata/domain/services/protocols/__init__.py
# AÇIKLAMA: Servis arayüzleri — structural typing (Protocol)
# Taşınan ve absolute importlara dönüştürülen eski protocols.py içeriği.

from typing import Any, Protocol, runtime_checkable

from bb_paxdata.application.domain.models.ai_analysis import AIAnalysisResult
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.anomaly import (
    AnomalyResult as _CanonicalAnomalyResult,
)
from bb_paxdata.application.domain.models.calibration import CalibrationReport
from bb_paxdata.application.domain.models.dki import (
    DynamicPositionResult,
    LLMPositionEstimate,
    PositionCalibration,
    SegmentWindow,
    SemanticShiftResult,
    SpeakerTrajectory,
)
from bb_paxdata.application.domain.models.human_review import HumanReview

# Re-export canonical AnomalyResult for backward compatibility
AnomalyResult = _CanonicalAnomalyResult


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


@runtime_checkable
class HumanReviewRepositoryProtocol(Protocol):
    async def save(self, review: HumanReview) -> None: ...
    async def get_by_analysis_id(self, analysis_id: str) -> list[HumanReview]: ...
    async def get_disagreements_for_prompt(
        self, prompt_version: str, limit: int = 50
    ) -> list[HumanReview]: ...
    async def get_reviews_for_prompt(
        self, prompt_version: str, limit: int = 100
    ) -> list[HumanReview]: ...
    async def get_gold_standard_examples(
        self, frame_type: str | None = None, limit: int = 5
    ) -> list[HumanReview]: ...


@runtime_checkable
class CalibrationReportRepositoryProtocol(Protocol):
    async def save(self, report: CalibrationReport) -> None: ...
    async def get_latest(self, prompt_version: str) -> CalibrationReport | None: ...
