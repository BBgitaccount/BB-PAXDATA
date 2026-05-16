from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class WordfishParams(BaseModel):
    """Parameters for the Wordfish EM algorithm."""

    model_config = ConfigDict(frozen=True)

    max_iter: int = Field(default=100, ge=10)
    tolerance: float = Field(default=1e-6, gt=0.0)
    verbose: bool = False

    # Regularization to prevent numerical overflow
    alpha_prior: float = Field(
        default=0.0, description="L2 regularization on document effects"
    )
    beta_prior: float = Field(
        default=0.0, description="L2 regularization on discrimination params"
    )


class SpeakerPosition(BaseModel):
    """Latent position and component scores for a speaker in a session."""

    model_config = ConfigDict(frozen=True, strict=True)

    speaker_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)

    # Raw component scores
    wordfish_theta: float = Field(..., description="Latent position from Wordfish")
    wordscores_t: float | None = Field(
        None, description="Calibrated Wordscores position"
    )
    stance_density: float = Field(default=0.0, ge=0.0)
    engagement_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Composite
    sbi: float = Field(..., description="Speaker-Based Index")

    # Wordshoal
    session_deviation: float | None = Field(None, description="ψᵢⱼ − θᵢ deviation")

    # Metadata weights
    alpha: float = Field(default=0.6, ge=0.0, le=1.0)
    beta: float = Field(default=0.25, ge=0.0, le=1.0)
    gamma: float = Field(default=0.15, ge=0.0, le=1.0)

    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def recalibrate_weights(
        self, alpha: float, beta: float, gamma: float
    ) -> SpeakerPosition:
        """Return new instance with updated weights and recalculated SBI."""
        if not abs(alpha + beta + gamma - 1.0) < 1e-9:
            raise ValueError("Weights must sum to 1.0")

        new_sbi = (
            alpha * self.wordfish_theta
            + beta * self.stance_density
            + gamma * self.engagement_score
        )
        return self.model_copy(
            update={"alpha": alpha, "beta": beta, "gamma": gamma, "sbi": new_sbi}
        )


class SBIResult(BaseModel):
    """Enveloping result for Speaker-Based Index calculations across multiple speakers."""

    model_config = ConfigDict(frozen=True, strict=True)

    positions: Sequence[SpeakerPosition]
    calibration_source: str = Field(
        default="wordfish_default", description="wordfish | wordscores | llm_hybrid"
    )
    pipeline_version: str = Field(default="sbi@v1.0")
    anomaly_flags: Sequence[str] = Field(default_factory=list)
