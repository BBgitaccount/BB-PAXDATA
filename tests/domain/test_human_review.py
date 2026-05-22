# tests/domain/test_human_review.py
from datetime import datetime

import pytest
from bb_paxdata.domain.models.calibration import CalibrationReport
from bb_paxdata.domain.models.human_review import (
    AgreementStatus,
    HumanReview,
    RiskLevel,
)
from pydantic import ValidationError


def test_human_review_immutability() -> None:
    """Model frozen=True olduğu için doğrudan atama exception fırlatmalı."""
    review = HumanReview(
        analysis_id="analysis_123",
        reviewer_id="reviewer_456",
        agreement_status=AgreementStatus.AGREED,
    )
    with pytest.raises(Exception):
        review.reviewer_id = "reviewer_new"  # type: ignore[misc]


def test_human_review_validation_ranges() -> None:
    """human_sbi_score ve human_sentiment_score değer sınırları dışındaysa validation hatası vermeli."""
    # SBI score invalid (> 100)
    with pytest.raises(ValidationError):
        HumanReview(
            analysis_id="analysis_123",
            reviewer_id="reviewer_456",
            agreement_status=AgreementStatus.DISAGREED,
            human_sbi_score=105.0,
        )

    # SBI score invalid (< -100)
    with pytest.raises(ValidationError):
        HumanReview(
            analysis_id="analysis_123",
            reviewer_id="reviewer_456",
            agreement_status=AgreementStatus.DISAGREED,
            human_sbi_score=-105.0,
        )

    # Sentiment score invalid (> 1.0)
    with pytest.raises(ValidationError):
        HumanReview(
            analysis_id="analysis_123",
            reviewer_id="reviewer_456",
            agreement_status=AgreementStatus.DISAGREED,
            human_sentiment_score=1.5,
        )

    # Sentiment score invalid (< -1.0)
    with pytest.raises(ValidationError):
        HumanReview(
            analysis_id="analysis_123",
            reviewer_id="reviewer_456",
            agreement_status=AgreementStatus.DISAGREED,
            human_sentiment_score=-1.5,
        )


def test_human_review_sbi_disagreement_and_delta() -> None:
    """has_sbi_disagreement ve sbi_delta computed_fields doğru çalışmalı."""
    # No values -> no disagreement
    r_empty = HumanReview(
        analysis_id="analysis_123",
        reviewer_id="reviewer_456",
        agreement_status=AgreementStatus.AGREED,
    )
    assert not r_empty.has_sbi_disagreement
    assert r_empty.sbi_delta is None

    # Tolerable difference (<= 5)
    r_tolerable = HumanReview(
        analysis_id="analysis_123",
        reviewer_id="reviewer_456",
        agreement_status=AgreementStatus.AGREED,
        ai_sbi_score=20.0,
        human_sbi_score=24.5,
    )
    assert not r_tolerable.has_sbi_disagreement
    assert r_tolerable.sbi_delta == pytest.approx(4.5)

    # Untolerable difference (> 5)
    r_disagree = HumanReview(
        analysis_id="analysis_123",
        reviewer_id="reviewer_456",
        agreement_status=AgreementStatus.DISAGREED,
        ai_sbi_score=20.0,
        human_sbi_score=25.1,
    )
    assert r_disagree.has_sbi_disagreement
    assert r_disagree.sbi_delta == pytest.approx(5.1)


def test_human_review_frame_and_risk_disagreement() -> None:
    """has_frame_disagreement ve has_risk_disagreement computed_fields doğru çalışmalı."""
    # Frame disagreement
    r_frame = HumanReview(
        analysis_id="analysis_123",
        reviewer_id="reviewer_456",
        agreement_status=AgreementStatus.PARTIAL,
        ai_dominant_frame="conflict",
        human_dominant_frame="cooperation",
    )
    assert r_frame.has_frame_disagreement

    r_frame_same = HumanReview(
        analysis_id="analysis_123",
        reviewer_id="reviewer_456",
        agreement_status=AgreementStatus.AGREED,
        ai_dominant_frame="conflict",
        human_dominant_frame="conflict",
    )
    assert not r_frame_same.has_frame_disagreement

    # Risk disagreement
    r_risk = HumanReview(
        analysis_id="analysis_123",
        reviewer_id="reviewer_456",
        agreement_status=AgreementStatus.PARTIAL,
        ai_risk_level=RiskLevel.LOW,
        human_risk_level=RiskLevel.HIGH,
    )
    assert r_risk.has_risk_disagreement

    r_risk_same = HumanReview(
        analysis_id="analysis_123",
        reviewer_id="reviewer_456",
        agreement_status=AgreementStatus.AGREED,
        ai_risk_level=RiskLevel.LOW,
        human_risk_level=RiskLevel.LOW,
    )
    assert not r_risk_same.has_risk_disagreement


def test_calibration_report_disagreement_rate_and_reliability() -> None:
    """CalibrationReport properties (disagreement_rate, is_reliable) doğru hesaplanmalı."""
    report = CalibrationReport(
        prompt_version="sentence_analysis@v1.2",
        evaluation_period_start=datetime.utcnow(),
        evaluation_period_end=datetime.utcnow(),
        total_reviews=10,
        total_disagreements=3,
        cohens_kappa_frame=0.72,
        cohens_kappa_risk=0.81,
    )
    assert report.disagreement_rate == 0.3
    assert report.is_reliable

    # Test not reliable due to one low kappa
    unreliable_report = CalibrationReport(
        prompt_version="sentence_analysis@v1.2",
        evaluation_period_start=datetime.utcnow(),
        evaluation_period_end=datetime.utcnow(),
        total_reviews=10,
        total_disagreements=3,
        cohens_kappa_frame=0.61,  # <= 0.67
        cohens_kappa_risk=0.81,
    )
    assert not unreliable_report.is_reliable

    # Test total reviews is 0
    empty_report = CalibrationReport(
        prompt_version="sentence_analysis@v1.2",
        evaluation_period_start=datetime.utcnow(),
        evaluation_period_end=datetime.utcnow(),
        total_reviews=0,
    )
    assert empty_report.disagreement_rate == 0.0
    assert not empty_report.is_reliable
