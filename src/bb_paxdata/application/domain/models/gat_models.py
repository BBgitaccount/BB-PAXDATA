"""GAT Embedding domain model — 256-dim output vector with anomaly score.

This module defines the domain-level GATEmbedding model used throughout the
BB-PAXDATA pipeline. It enforces dimensionality constraints (EMBEDDING_DIM=256),
L2-norm non-degeneracy, and anomaly score range [0.0, 1.0] / sentinel -1.0.

Note: -1.0 is used as a sentinel value when the normal prototype is unavailable
(e.g., before contrastive training). All downstream consumers must handle this.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Constants ──────────────────────────────────────────────────────────────────
EMBEDDING_DIM: int = 256
"""Expected dimensionality of the GAT output embedding vector."""

ANOMALY_SENTINEL: float = -1.0
"""Sentinel value indicating anomaly score computation was not possible."""


# ── Domain Model ───────────────────────────────────────────────────────────────


class GATEmbedding(BaseModel):
    """256-dimensional GAT output vector with anomaly score for a speaker.

    This is a frozen domain entity. Once created it should not be mutated.

    Attributes:
        actor_id: Speaker/Country entity ID.
        session_id: Analysis session ID.
        embedding: 256-dimensional GAT output vector (L2-normalized at inference).
        characteristic_concepts: Top-K concept IDs by attention weight from GAT
            layer 1 (multi-head averaged). May be empty for isolated actors.
        anomaly_score: Cosine distance from normal prototype in embedding space.
            Value is in [0.0, 1.0] when prototype is available, or -1.0 as
            sentinel when prototype has not been computed (pre-training).
            -1.0 must be handled by SBICalculator (see FINDING M-06).
        computed_at: UTC timestamp of embedding computation.
    """

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        arbitrary_types_allowed=True,
    )

    actor_id: str = Field(..., min_length=1, description="Speaker/Country entity ID")
    session_id: str = Field(..., min_length=1, description="Analysis session ID")

    embedding: Annotated[
        np.ndarray,
        Field(
            description=f"{EMBEDDING_DIM}-dimensional GAT output vector (L2-normalized)",
        ),
    ]

    characteristic_concepts: list[str] = Field(
        default_factory=list,
        description=(
            "Top-K concept IDs by attention weight from GAT layer 1 "
            "(multi-head averaged); may be empty for isolated actors"
        ),
    )

    anomaly_score: float = Field(
        default=ANOMALY_SENTINEL,
        description=(
            "Cosine distance from normal prototype in embedding space. "
            f"In [0.0, 1.0] when available; {ANOMALY_SENTINEL} if prototype missing."
        ),
    )

    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ── Validators ──────────────────────────────────────────────────────────

    @field_validator("anomaly_score", mode="before")
    @classmethod
    def _coerce_anomaly_score(cls, v: float) -> float:
        """Allow -1.0 sentinel; validate [0.0, 1.0] otherwise.

        The pydantic ``ge=0.0, le=1.0`` constraint would reject -1.0, so we
        use ``mode='before'`` to bypass for the sentinel case and validate
        the range for all other values.
        """
        if v == ANOMALY_SENTINEL:
            return v
        if not isinstance(v, int | float):
            raise TypeError(f"anomaly_score must be numeric, got {type(v).__name__}")
        fv = float(v)
        if not 0.0 <= fv <= 1.0:
            raise ValueError(
                f"anomaly_score must be in [0.0, 1.0] or sentinel {ANOMALY_SENTINEL}; "
                f"got {fv}"
            )
        return fv

    @field_validator("embedding", mode="before")
    @classmethod
    def _validate_embedding_shape_and_type(cls, v: Any) -> np.ndarray:
        """Validate and convert embedding to numpy array with correct shape."""
        if isinstance(v, np.ndarray):
            arr = v
        elif isinstance(v, list):
            arr = np.array(v, dtype=np.float32)
        else:
            raise TypeError(
                f"embedding must be np.ndarray or list[float], got {type(v).__name__}"
            )

        if arr.ndim != 1:
            raise ValueError(f"embedding must be 1-dimensional, got {arr.ndim}D")
        if arr.shape[0] != EMBEDDING_DIM:
            raise ValueError(
                f"embedding must have {EMBEDDING_DIM} dimensions, got {arr.shape[0]}"
            )
        if arr.dtype != np.float32:
            arr = arr.astype(np.float32)

        return arr

    @field_validator("embedding")
    @classmethod
    def _validate_embedding_non_degenerate(cls, v: np.ndarray) -> np.ndarray:
        """Reject near-zero embedding vectors (degenerate model output)."""
        norm_sq = float(np.sum(v * v))
        if norm_sq < 1e-12:
            raise ValueError(
                f"Embedding vector is near-zero (norm²={norm_sq:.2e}). "
                "Possible degenerate input from all-zero initial features."
            )
        return v
