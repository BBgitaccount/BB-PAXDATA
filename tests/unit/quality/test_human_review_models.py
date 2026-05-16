from uuid import uuid4

import pytest
from bb_paxdata.domain.enums import Priority, ReviewStatus, ReviewType
from bb_paxdata.domain.utils.hash import compute_audit_hash
from bb_paxdata.quality.human_review import (
    HumanReviewRequest,
    HumanReviewResult,
    MetricOverride,
)


def test_metric_override_immutable():
    override = MetricOverride(
        original_value=0.5,
        overridden_value=0.8,
        confidence=0.9,
        justification="Human review",
    )
    with pytest.raises(
        Exception
    ):  # Pydantic v2 raises ValidationError or similar on mutation if frozen
        override.confidence = 1.0


def test_human_review_request_model():
    analysis_id = uuid4()
    request = HumanReviewRequest(
        analysis_id=analysis_id,
        review_type=ReviewType.CONFIRMATORY,
        priority=Priority.HIGH,
        submitted_by="test_user",
    )
    assert request.analysis_id == analysis_id
    assert request.submitted_at is not None


def test_human_review_result_hash():
    review_id = uuid4()
    analysis_id = uuid4()

    # Test deterministic hash
    hash1 = compute_audit_hash(str(review_id), str(analysis_id), "approved")
    hash2 = compute_audit_hash(str(review_id), str(analysis_id), "approved")
    assert hash1 == hash2

    result = HumanReviewResult(
        review_id=review_id,
        analysis_id=analysis_id,
        reviewer_id="reviewer_1",
        status=ReviewStatus.APPROVED,
        metric_overrides={},
        audit_hash=hash1,
    )
    assert result.audit_hash == hash1
