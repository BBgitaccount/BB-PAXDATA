from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class WordfishParams(BaseModel):
    """Parameters for the Wordfish EM algorithm."""

    model_config = ConfigDict(frozen=False)

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

    model_config = ConfigDict(frozen=False, strict=True)

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
    # (M-10) Interim weights — GAT signal experimental, delta kept low.
    # The epsilon for sum-of-weights validation is 1e-6 (M-03).
    alpha: float = Field(
        default=0.55, ge=0.0, le=1.0, description="Wordfish theta weight"
    )
    beta: float = Field(
        default=0.22, ge=0.0, le=1.0, description="Stance density weight"
    )
    gamma: float = Field(
        default=0.18,
        ge=0.0,
        le=1.0,
        description="Engagement score weight (post-M-03 correction)",
    )
    delta: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="GAT anomaly weight (experimental; increase after HITL validation)",
    )

    gat_anomaly_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="GAT anomaly score for this speaker"
    )

    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # (M-03) Relaxed epsilon for float64 weight sum validation
    _WEIGHT_SUM_EPSILON: float = 1e-6

    def recalibrate_weights(
        self, alpha: float, beta: float, gamma: float, delta: float = 0.05
    ) -> SpeakerPosition:
        """Return new instance with updated weights and recalculated SBI.

        Args:
            alpha: Weight for wordfish_theta component.
            beta:  Weight for stance_density component.
            gamma: Weight for engagement_score component.
            delta: Weight for gat_anomaly_score component (default 0.05).

        Raises:
            ValueError: If weights do not sum to 1.0 within epsilon tolerance.
        """
        total = alpha + beta + gamma + delta
        if abs(total - 1.0) >= self._WEIGHT_SUM_EPSILON:
            raise ValueError(
                f"Weights must sum to 1.0 \u00b1 {self._WEIGHT_SUM_EPSILON}. "
                f"Got {total:.10f} (delta from 1.0: {abs(total - 1.0):.2e})"
            )

        gat_val = self.gat_anomaly_score

        # (M-06) When GAT data is unavailable, renormalize remaining weights
        # to preserve SBI scale. Otherwise the effective weight sum becomes
        # alpha+beta+gamma = 0.85 instead of 1.0, systematically deflating SBI.
        if gat_val is not None and gat_val >= 0.0:
            new_sbi = (
                alpha * self.wordfish_theta
                + beta * self.stance_density
                + gamma * self.engagement_score
                + delta * gat_val
            )
        else:
            remaining = alpha + beta + gamma
            if remaining < self._WEIGHT_SUM_EPSILON:
                raise ValueError(
                    "Non-GAT weights sum to zero; cannot compute SBI without GAT data."
                )
            new_sbi = (
                (alpha / remaining) * self.wordfish_theta
                + (beta / remaining) * self.stance_density
                + (gamma / remaining) * self.engagement_score
            )

        return self.model_copy(
            update={
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
                "delta": delta,
                "sbi": new_sbi,
            }
        )


class SBIResult(BaseModel):
    """Enveloping result for Speaker-Based Index calculations across multiple speakers."""

    model_config = ConfigDict(frozen=False, strict=True)

    positions: Sequence[SpeakerPosition]
    calibration_source: str = Field(
        default="wordfish_default", description="wordfish | wordscores | llm_hybrid"
    )
    pipeline_version: str = Field(default="sbi@v1.0")
    anomaly_flags: Sequence[str] = Field(default_factory=list)
