# src/bb_paxdata/domain/services/protocols/judge_protocols.py
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(strict=True)

    semantic_shift_score: float = Field(..., ge=0.0, le=1.0)
    is_consistent: bool
    calibration_drift: float = Field(..., ge=-1.0, le=1.0)
    reasoning: str = Field(..., max_length=2000)
    prompt_hash: str
    response_hash: str
    model_used: str
    inference_time_ms: float


class BaselineMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    historical_sentiment_avg: float
    historical_risk_avg: float
    historical_frame_mode: str
    window_size: int
    panel_ids_in_window: list[str]


class JudgeProtocol(Protocol):
    async def evaluate(
        self,
        speaker_name: str,
        country: str,
        sentence_text: str,
        pipeline_sentiment: str,
        pipeline_risk_score: float,
        pipeline_frame: str,
        baseline: BaselineMetrics,
    ) -> JudgeVerdict: ...
