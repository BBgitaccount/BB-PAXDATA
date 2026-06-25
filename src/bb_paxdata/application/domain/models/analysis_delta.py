# CIDDI-9 Caching Analysis:
# Q1. AnalysisDelta is Pydantic BaseModel with model_config = ConfigDict(frozen=True) → SCENARIO B.
# Q2. Pydantic ^2.7 (v2). Import is `from pydantic import BaseModel`, not pydantic.v1.
# Q3. Expensive @property methods identified:
#       - most_drifted_speaker: iterates common_speakers (O(n)), does dict lookups per speaker.
#       - most_drifted_dimension: 4x sum(abs) over normalized dicts + max() over 5 keys (O(n)).
#       - total_significant_changes: len() call on list → O(1), NOT cached.
# Q4. Other delta classes (SignificantChange, MetricDelta, SpeechActDistributionDelta,
#     NarrativeLayerDelta) are frozen dataclasses with no @property methods — no action needed.
# Q5. No existing caching mechanism found.
# Strategy: SCENARIO B — frozen Pydantic v2 model. Use PrivateAttr + model_post_init +
#     object.__setattr__ to pre-compute expensive properties once at construction time.
#     @cached_property MUST NOT be used on frozen models (raises TypeError on first access).

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class RiskAssessmentLevel(StrEnum):
    HIGH_RISK_ESCALATION = "HIGH_RISK_ESCALATION"
    RISK_DEESCALATION = "RISK_DEESCALATION"
    MODERATE_CONCERN = "MODERATE_CONCERN"
    STABLE = "STABLE"


@dataclass(frozen=True)
class SignificantChange:
    dimension: str
    speaker_id: str | None
    raw_delta: float | None
    normalized_delta: float | None


@dataclass(frozen=True)
class MetricDelta:
    metric_name: str
    value_a: float | None
    value_b: float | None
    delta: float | None
    delta_normalized: float | None
    is_significant: bool
    threshold: float


@dataclass(frozen=True)
class SpeechActDistributionDelta:
    speaker_id: str
    distribution_a: dict[str, float]
    distribution_b: dict[str, float]
    delta_distribution: dict[str, float]
    most_changed_type: str | None  # key with max abs(delta_distribution[k])
    change_magnitude: float  # abs(delta_distribution[most_changed_type])


@dataclass(frozen=True)
class NarrativeLayerDelta:
    speaker_id: str
    layer_weights_a: dict[str, float]
    layer_weights_b: dict[str, float]
    delta_weights: dict[str, float]
    dominant_layer_change: tuple[str, float] | None  # (layer, delta), signed


class AnalysisDelta(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_a_id: str = Field(...)
    session_b_id: str = Field(...)
    comparison_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    delta_sbi: dict[str, float] = Field(default_factory=dict)
    delta_sbi_normalized: dict[str, float] = Field(default_factory=dict)
    delta_sbi_significant: dict[str, bool] = Field(default_factory=dict)

    delta_dki: dict[str, float] = Field(default_factory=dict)
    delta_dki_normalized: dict[str, float] = Field(default_factory=dict)
    delta_dki_significant: dict[str, bool] = Field(default_factory=dict)

    delta_risk: float | None = Field(default=None)
    delta_risk_normalized: float | None = Field(default=None)
    delta_risk_significant: bool = Field(default=False)

    delta_hedging: dict[str, float] = Field(default_factory=dict)
    delta_hedging_normalized: dict[str, float] = Field(default_factory=dict)
    delta_hedging_significant: dict[str, bool] = Field(default_factory=dict)

    delta_speech_act: dict[str, SpeechActDistributionDelta] = Field(
        default_factory=dict
    )
    delta_narrative: dict[str, NarrativeLayerDelta] = Field(default_factory=dict)

    significant_changes: list[SignificantChange] = Field(default_factory=list)

    speakers_in_a: frozenset[str] = Field(default_factory=frozenset)
    speakers_in_b: frozenset[str] = Field(default_factory=frozenset)
    common_speakers: frozenset[str] = Field(default_factory=frozenset)
    speakers_only_in_a: frozenset[str] = Field(default_factory=frozenset)
    speakers_only_in_b: frozenset[str] = Field(default_factory=frozenset)

    # Pre-computed fields for expensive properties (CIDDI-9).
    # PrivateAttr fields are not Pydantic-validated model fields — safe to set via
    # object.__setattr__ inside model_post_init even on a frozen model.
    _most_drifted_speaker: str | None = PrivateAttr(default=None)
    _most_drifted_dimension: str = PrivateAttr(default="")

    def model_post_init(self, __context: Any) -> None:
        """Pre-compute all O(n) derived values once at construction time. (CIDDI-9)

        object.__setattr__ is required here because the model is frozen=True.
        Directly assigning (self._field = ...) raises a Pydantic ValidationError.
        PrivateAttr fields are exempt from Pydantic's frozen enforcement, but the
        safe cross-version pattern is to always use object.__setattr__ for them.
        """
        object.__setattr__(
            self,
            "_most_drifted_speaker",
            self._compute_most_drifted_speaker(),
        )
        object.__setattr__(
            self,
            "_most_drifted_dimension",
            self._compute_most_drifted_dimension(),
        )

    # ── Internal computation methods (called once in model_post_init) ─────────

    def _compute_most_drifted_speaker(self) -> str | None:
        """Scan all common speakers and find the one with the highest combined drift.

        Called once at construction; result stored in _most_drifted_speaker.
        """
        if not self.common_speakers:
            return None
        drift_scores: dict[str, float] = {}
        for speaker in self.common_speakers:
            score = 0.0
            score += abs(self.delta_sbi_normalized.get(speaker, 0.0))
            score += abs(self.delta_dki_normalized.get(speaker, 0.0))
            score += abs(self.delta_hedging_normalized.get(speaker, 0.0))
            if speaker in self.delta_speech_act:
                score += self.delta_speech_act[speaker].change_magnitude
            drift_scores[speaker] = score
        return max(drift_scores, key=drift_scores.get) if drift_scores else None  # type: ignore[arg-type]

    def _compute_most_drifted_dimension(self) -> str:
        """Sum absolute normalized deltas across all dimensions and find the maximum.

        Called once at construction; result stored in _most_drifted_dimension.
        """
        dimension_drifts = {
            "SBI": sum(abs(v) for v in self.delta_sbi_normalized.values()),
            "DKI": sum(abs(v) for v in self.delta_dki_normalized.values()),
            "Risk": abs(self.delta_risk_normalized or 0.0),
            "Hedging": sum(abs(v) for v in self.delta_hedging_normalized.values()),
            "SpeechAct": sum(
                d.change_magnitude for d in self.delta_speech_act.values()
            ),
        }
        return max(dimension_drifts, key=dimension_drifts.get)  # type: ignore[arg-type]

    # ── Public property accessors (O(1) — read from pre-computed PrivateAttr) ─

    @property
    def most_drifted_speaker(self) -> str | None:
        """Speaker with the highest combined normalized drift score.

        Pre-computed at construction; O(1) access. (CIDDI-9)
        """
        return self._most_drifted_speaker

    @property
    def most_drifted_dimension(self) -> str:
        """Analysis dimension (SBI/DKI/Risk/Hedging/SpeechAct) with largest total drift.

        Pre-computed at construction; O(1) access. (CIDDI-9)
        """
        return self._most_drifted_dimension

    @property
    def total_significant_changes(self) -> int:
        # O(1) — len() on a list is constant time. Not cached intentionally.
        return len(self.significant_changes)
