import pytest

from bb_paxdata.application.domain.models.appraisal_vector import (
    AffectType,
    AppraisalDocumentResult,
    AppraisalVector,
    AppreciationType,
    EngagementType,
    JudgmentType,
)


def test_appraisal_vector_default_values():
    vector = AppraisalVector()
    assert vector.affect_score == 0.0
    assert vector.affect_type is None
    assert vector.affect_confidence == 0.0
    assert vector.judgment_score == 0.0
    assert vector.judgment_type is None
    assert vector.judgment_is_sanction is False
    assert vector.judgment_confidence == 0.0
    assert vector.appreciation_score == 0.0
    assert vector.appreciation_type is None
    assert vector.appreciation_confidence == 0.0
    assert vector.graduation_force == 0.0
    assert vector.graduation_force_direction is None
    assert vector.engagement_type == EngagementType.MONOGLOSS
    assert vector.engagement_confidence == 0.0
    assert not vector.has_any_detection
    assert vector.dominant_axis is None
    assert vector.weighted_intensity == 0.0


def test_appraisal_vector_with_detection():
    vector = AppraisalVector(
        affect_score=-0.5,
        affect_type=AffectType.SECURITY,
        affect_confidence=0.8,
        judgment_score=0.0,
        appreciation_score=0.2,
        appreciation_type=AppreciationType.VALUE,
        appreciation_confidence=0.4,
    )
    assert vector.has_any_detection
    # Dominant axis should be AFFECT because abs(-0.5 * 0.8) = 0.4, appreciation is abs(0.2 * 0.4) = 0.08
    assert vector.dominant_axis == "AFFECT"
    assert vector.weighted_intensity == pytest.approx(0.24)  # (0.4 + 0.08) / 2 = 0.24
    assert vector.is_negative_judgment_sanction is False


def test_appraisal_vector_negative_judgment_sanction():
    vector = AppraisalVector(
        judgment_score=-0.7,
        judgment_type=JudgmentType.SANCTION,
        judgment_is_sanction=True,
        judgment_confidence=0.9,
    )
    assert vector.is_negative_judgment_sanction


def test_to_dict_for_db():
    vector = AppraisalVector(
        affect_score=-0.5,
        affect_type=AffectType.SECURITY,
        affect_confidence=0.8,
        trigger_words=["concerned", "fear"],
    )
    db_dict = vector.to_dict_for_db()
    assert "trigger_words" not in db_dict
    assert db_dict["affect_score"] == -0.5
    assert db_dict["dominant_axis"] == "AFFECT"
    assert db_dict["weighted_intensity"] == 0.4
    assert db_dict["is_negative_judgment_sanction"] is False


def test_appraisal_document_result():
    vector1 = AppraisalVector(
        judgment_score=-0.7,
        judgment_type=JudgmentType.SANCTION,
        judgment_is_sanction=True,
        judgment_confidence=0.9,
    )
    vector2 = AppraisalVector(
        affect_score=0.5,
        affect_type=AffectType.HAPPINESS,
        affect_confidence=0.8,
    )
    doc_result = AppraisalDocumentResult(
        vectors=[
            ("seg-1", vector1),
            ("seg-2", vector2),
        ]
    )
    assert doc_result.judgment_sanction_count == 1
    assert doc_result.dominant_engagement == EngagementType.MONOGLOSS
    assert doc_result.coverage_rate == 1.0
