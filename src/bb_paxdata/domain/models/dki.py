from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class SegmentWindow(BaseModel):
    """Data structure for embedding context in semantic shift calculation."""

    model_config = ConfigDict(frozen=True)

    segment_ids: list[str]
    texts: list[str]
    speaker_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SemanticShiftResult(BaseModel):
    """Immutable result of semantic shift calculation (Azarbonyad 2017)."""

    model_config = ConfigDict(frozen=True)

    aggregate_shift: Annotated[float, Field(ge=0.0, le=2.0)]
    per_word_shifts: dict[str, float]
    idf_weights_used: dict[str, float]
    vocabulary_overlap_ratio: Annotated[float, Field(ge=0.0, le=1.0)]
    historical_window_count: int
    calculation_method: str = "azarbonyad_2017"


class DynamicPositionResult(BaseModel):
    """Result of speaker position time-series tracking (Poole-Rosenthal 1997)."""

    model_config = ConfigDict(frozen=True)

    speaker_id: str
    session_count: int
    raw_velocities: list[float]
    smoothed_velocities: list[float]
    current_velocity: float
    current_acceleration: float
    interpolation_count: int
    max_gap_days: float
    calculation_method: str = "poole_rosenthal_1997_sma"


class DKIComponents(BaseModel):
    """Individual factors contributing to the DKI score."""

    model_config = ConfigDict(frozen=True)

    velocity: float
    semantic_shift: float
    debate_loading: float
    raw_product: float


class DKIResult(BaseModel):
    """Composite Discourse-Kinetic Index (DKI) result."""

    model_config = ConfigDict(frozen=True)

    speaker_id: str
    session_id: str
    dki_score: float
    components: DKIComponents
    anomaly_flag: bool = False
    calculation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class LLMPositionEstimate(BaseModel):
    """Deterministic LLM-based position estimation (Cambridge Core 2026)."""

    model_config = ConfigDict(frozen=True)

    text_hash: str
    policy_dimension: str
    average_position: Annotated[float, Field(ge=0.0, le=100.0)]
    sentence_scores: list[
        dict[str, Any]
    ]  # [{"sentence": str, "position": int, "confidence": float, "rationale": str}]
    std_deviation: float
    prompt_version: str
    prompt_sha256: str
    model_name: str
    temperature: float = 0.0


class PositionCalibration(BaseModel):
    """Calibration report between LLM and Wordfish positions."""

    model_config = ConfigDict(frozen=True)

    pearson_r: float
    mean_absolute_error: float
    drift_detected: bool
    sample_size: int
    calibration_method: str = "cambridge_core_2026"


class SpeakerTrajectory(BaseModel):
    """Time-ordered sequence of positions for a speaker."""

    model_config = ConfigDict(frozen=True)

    speaker_id: str
    positions: Sequence[dict[str, Any]]  # [{"theta": float, "timestamp": datetime}]
