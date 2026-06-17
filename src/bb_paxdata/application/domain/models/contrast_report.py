from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from bb_paxdata.application.domain.models.analysis_delta import (
    AnalysisDelta,
    RiskAssessmentLevel,
)


class ContrastReport(BaseModel):
    model_config = ConfigDict(frozen=False)

    delta: AnalysisDelta = Field(...)

    narrative_summary: str | None = Field(
        default=None,
        description="LLM-generated narrative. None if not requested or generation failed.",
    )
    narrative_summary_skipped: bool = Field(default=False)
    narrative_summary_failed: bool = Field(default=False)
    narrative_summary_model: str = Field(default="")
    narrative_summary_timestamp: datetime | None = Field(default=None)

    @property
    def most_drifted_speaker(self) -> str | None:
        return self.delta.most_drifted_speaker

    @property
    def most_drifted_dimension(self) -> str:
        return self.delta.most_drifted_dimension

    key_insights: list[str] = Field(default_factory=list)
    risk_assessment: RiskAssessmentLevel | None = Field(default=None)
    risk_level_changed: bool = Field(default=False)
    recommendation: str | None = Field(default=None)

    report_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this contrast report",
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
