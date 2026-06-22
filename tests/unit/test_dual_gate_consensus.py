from unittest.mock import MagicMock

import pytest

from bb_paxdata.application.consensus.dual_gate import (
    ConsensusLevel,
    DualGateConsensusLayer,
)
from bb_paxdata.application.domain.models.anomaly import AnomalyValidationDecision


def make_det(has_anomaly: bool):
    r = MagicMock()
    r.has_anomaly = has_anomaly
    return r


def make_ai(decision: AnomalyValidationDecision, coherence: float = 0.7):
    r = MagicMock()
    r.decision = decision
    r.coherence_score = coherence
    r.reasoning = "test"
    r.detected_subtype = None
    return r


@pytest.fixture
def layer():
    return DualGateConsensusLayer()


@pytest.mark.asyncio
async def test_hard_anomaly_when_both_confirm(layer):
    result = await layer.decide(
        deterministic=make_det(True),
        ai_validation=make_ai(AnomalyValidationDecision.CONFIRMED),
    )
    assert result.level == ConsensusLevel.HARD_ANOMALY
    assert result.send_to_hitl is True


@pytest.mark.asyncio
async def test_soft_anomaly_when_ai_dismisses(layer):
    result = await layer.decide(
        deterministic=make_det(True),
        ai_validation=make_ai(AnomalyValidationDecision.DISMISSED),
    )
    assert result.level == ConsensusLevel.SOFT_ANOMALY
    assert result.send_to_hitl is False


@pytest.mark.asyncio
async def test_critical_when_escalated(layer):
    result = await layer.decide(
        deterministic=make_det(True),
        ai_validation=make_ai(AnomalyValidationDecision.ESCALATED),
    )
    assert result.level == ConsensusLevel.CRITICAL_ANOMALY
    assert result.send_to_hitl is True


@pytest.mark.asyncio
async def test_clean_when_no_anomaly_and_dismissed(layer):
    result = await layer.decide(
        deterministic=make_det(False),
        ai_validation=make_ai(AnomalyValidationDecision.DISMISSED, coherence=0.95),
    )
    assert result.level == ConsensusLevel.CLEAN
    assert result.send_to_hitl is False


@pytest.mark.asyncio
async def test_coherence_penalty_on_conflict(layer):
    """Det anomali VAR ama AI dismiss → coherence penalized."""
    result = await layer.decide(
        deterministic=make_det(True),
        ai_validation=make_ai(AnomalyValidationDecision.DISMISSED, coherence=0.8),
    )
    assert result.coherence_score < 0.8  # penaltı uygulandı
