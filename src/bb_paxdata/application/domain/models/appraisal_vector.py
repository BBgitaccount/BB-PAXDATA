from enum import StrEnum
from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field


class AffectType(StrEnum):
    HAPPINESS = "happiness"
    SECURITY = "security"
    SATISFACTION = "satisfaction"


class JudgmentType(StrEnum):
    ESTEEM = "esteem"
    SANCTION = "sanction"


class AppreciationType(StrEnum):
    REACTION = "reaction"
    COMPOSITION = "composition"
    VALUE = "value"


class EngagementType(StrEnum):
    MONOGLOSS = "monogloss"
    HETEROGLOSS = "heterogloss"


class AppraisalVector(BaseModel):
    model_config = ConfigDict(frozen=False, strict=True)

    # AFFECT (Emotional response)
    affect_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    affect_type: AffectType | None = Field(default=None)
    affect_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # JUDGMENT (Ethical / Moral evaluation)
    judgment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    judgment_type: JudgmentType | None = Field(default=None)
    judgment_is_sanction: bool = Field(default=False)
    judgment_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # APPRECIATION (Aesthetic / Value judgment)
    appreciation_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    appreciation_type: AppreciationType | None = Field(default=None)
    appreciation_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # GRADUATION (Intensity / Force / Focus modifier)
    graduation_force: float = Field(default=0.0, ge=0.0, le=1.0)
    graduation_force_direction: str | None = Field(default=None)  # e.g., "up" or "down"
    graduation_focus: str | None = Field(default=None)

    # ENGAGEMENT (Monogloss / Heterogloss alignment)
    engagement_type: EngagementType = Field(default=EngagementType.MONOGLOSS)
    engagement_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Metadata & Provenance
    source_segment_id: str | None = Field(default=None)
    model_version: str = Field(default="lexicon-v1.0")
    trigger_words: list[str] = Field(default_factory=list)

    @property
    def has_any_detection(self) -> bool:
        """Check if any appraisal features have been detected."""
        return (
            self.affect_type is not None
            or self.judgment_type is not None
            or self.appreciation_type is not None
            or self.graduation_force > 0.0
            or self.engagement_confidence > 0.0
        )

    @property
    def dominant_axis(self) -> str | None:
        """Determine the appraisal axis with the highest absolute confidence-weighted score."""
        if not self.has_any_detection:
            return None

        scores = {
            "AFFECT": abs(self.affect_score * self.affect_confidence),
            "JUDGMENT": abs(self.judgment_score * self.judgment_confidence),
            "APPRECIATION": abs(self.appreciation_score * self.appreciation_confidence),
        }

        max_axis = max(scores, key=lambda k: scores[k])
        if scores[max_axis] == 0.0:
            # Fallback to axes with type assignments if absolute scores are zero
            if self.affect_type is not None:
                return "AFFECT"
            if self.judgment_type is not None:
                return "JUDGMENT"
            if self.appreciation_type is not None:
                return "APPRECIATION"
            return None

        return max_axis

    @property
    def weighted_intensity(self) -> float:
        """Calculate weighted intensity across AFFECT, JUDGMENT, and APPRECIATION."""
        scores = [
            abs(self.affect_score * self.affect_confidence),
            abs(self.judgment_score * self.judgment_confidence),
            abs(self.appreciation_score * self.appreciation_confidence),
        ]
        active_scores = [s for s in scores if s > 0.0]
        if not active_scores:
            return 0.0
        return sum(active_scores) / len(active_scores)

    @property
    def is_negative_judgment_sanction(self) -> bool:
        """Check if the vector represents a negative social sanction judgment."""
        return self.judgment_type == JudgmentType.SANCTION and self.judgment_score < 0.0

    def to_dict_for_db(self) -> dict:
        """Serialize for JSONB storage, excluding list/unserializable fields and adding properties."""
        base = self.model_dump(exclude={"trigger_words"})
        base["dominant_axis"] = self.dominant_axis
        base["weighted_intensity"] = self.weighted_intensity
        base["is_negative_judgment_sanction"] = self.is_negative_judgment_sanction
        return base


class AppraisalDocumentResult(BaseModel):
    model_config = ConfigDict(frozen=False)

    vectors: list[tuple[str, AppraisalVector]] = Field(default_factory=list)

    @cached_property
    def judgment_sanction_count(self) -> int:
        """Count the number of segments with negative social sanction judgment."""
        return sum(1 for _, v in self.vectors if v.is_negative_judgment_sanction)

    @cached_property
    def dominant_engagement(self) -> EngagementType:
        """Determine the dominant engagement type across the document."""
        if not self.vectors:
            return EngagementType.MONOGLOSS
        mono = sum(
            1 for _, v in self.vectors if v.engagement_type == EngagementType.MONOGLOSS
        )
        hetero = len(self.vectors) - mono
        return (
            EngagementType.MONOGLOSS if mono >= hetero else EngagementType.HETEROGLOSS
        )

    @property
    def coverage_rate(self) -> float:
        """Return the percentage of segments containing any appraisal detection."""
        if not self.vectors:
            return 0.0
        detected = sum(1 for _, v in self.vectors if v.has_any_detection)
        return detected / len(self.vectors)
