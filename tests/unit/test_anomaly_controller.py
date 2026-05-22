from unittest.mock import AsyncMock, MagicMock

import pytest
from bb_paxdata.domain.models.anomaly import AnomalyResult
from bb_paxdata.infrastructure.ai.anomaly_controller import (
    AIAnomalyController,
    AnomalyValidationDecision,
)
from bb_paxdata.infrastructure.ai.base import CompletionResult


@pytest.fixture
def mock_ai_client():
    client = AsyncMock()
    content = """{
        "decision": "DISMISSED",
        "coherence_score": 0.85,
        "reasoning": "Bu ironi stratejisidir, anomali değil.",
        "detected_subtype": "irony",
        "confidence": 0.9
    }"""
    client.complete.return_value = CompletionResult(
        content=content,
        parsed=None,
        backend="mock",
        model="mock",
        tokens_used=10,
        latency_ms=10,
        success=True,
    )
    return client


@pytest.fixture
def mock_recovery(mock_ai_client):
    recovery = MagicMock()
    recovery.recover.return_value = {
        "decision": "DISMISSED",
        "coherence_score": 0.85,
        "reasoning": "Bu ironi stratejisidir, anomali değil.",
        "detected_subtype": "irony",
        "confidence": 0.9,
    }
    return recovery


@pytest.mark.asyncio
async def test_false_positive_dismissed(mock_ai_client, mock_recovery):
    """Deterministik anomali AI tarafından ironi olarak dismiss edilmeli."""
    controller = AIAnomalyController(
        ai_client=mock_ai_client,
        recovery_engine=mock_recovery,
    )
    det_result = MagicMock(spec=AnomalyResult)
    det_result.has_anomaly = True

    sentence = MagicMock()
    sentence.id = "test-id"
    sentence.text = "Barış için savaşmaya hazırız."

    result = await controller.validate(
        sentence=sentence,
        deterministic_result=det_result,
        context_sentences=[],
    )

    assert result.decision == AnomalyValidationDecision.DISMISSED
    assert result.coherence_score == pytest.approx(0.85)
    assert result.detected_subtype == "irony"


@pytest.mark.asyncio
async def test_graceful_failure_returns_inconclusive(mock_recovery):
    """AI çağrısı başarısız olursa INCONCLUSIVE dönmeli, pipeline durmamalı."""
    failing_client = AsyncMock()
    failing_client.complete.side_effect = RuntimeError("API timeout")

    controller = AIAnomalyController(
        ai_client=failing_client,
        recovery_engine=mock_recovery,
    )
    det_result = MagicMock(spec=AnomalyResult)
    det_result.has_anomaly = False

    sentence = MagicMock()
    sentence.id = "fail-id"
    sentence.text = "Test cümlesi."

    result = await controller.validate(
        sentence=sentence,
        deterministic_result=det_result,
        context_sentences=[],
    )

    assert result.decision == AnomalyValidationDecision.INCONCLUSIVE
    assert result.confidence == 0.0
