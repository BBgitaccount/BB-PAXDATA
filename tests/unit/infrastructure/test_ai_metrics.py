import asyncio
from unittest.mock import AsyncMock

import pytest
import structlog
from httpx import Request, Response

from bb_paxdata.infrastructure.ai.base import ai_call_instrumented
from bb_paxdata.infrastructure.observability.metrics import get_metrics

logger = structlog.get_logger("test_ai_metrics")


@pytest.mark.asyncio
async def test_ai_call_instrumented_success() -> None:
    # Get the metrics collector
    metrics = get_metrics()

    # Record baseline
    base_prompt = (
        metrics.registry.get_sample_value(
            "ai_tokens_total",
            {
                "backend": "test_backend",
                "model": "test_model",
                "token_type": "prompt",
            },
        )
        or 0.0
    )
    base_completion = (
        metrics.registry.get_sample_value(
            "ai_tokens_total",
            {
                "backend": "test_backend",
                "model": "test_model",
                "token_type": "completion",
            },
        )
        or 0.0
    )
    base_total = (
        metrics.registry.get_sample_value(
            "ai_tokens_total",
            {
                "backend": "test_backend",
                "model": "test_model",
                "token_type": "total",
            },
        )
        or 0.0
    )
    base_request = (
        metrics.registry.get_sample_value(
            "ai_request_duration_seconds_count",
            {"backend": "test_backend", "model": "test_model", "status": "success"},
        )
        or 0.0
    )

    async with ai_call_instrumented("test_backend", "test_model", logger) as record:
        record.prompt_tokens = 10
        record.completion_tokens = 20
        await asyncio.sleep(0.01)

    # Verify that the values have updated
    new_prompt = metrics.registry.get_sample_value(
        "ai_tokens_total",
        {
            "backend": "test_backend",
            "model": "test_model",
            "token_type": "prompt",
        },
    )
    new_completion = metrics.registry.get_sample_value(
        "ai_tokens_total",
        {
            "backend": "test_backend",
            "model": "test_model",
            "token_type": "completion",
        },
    )
    new_total = metrics.registry.get_sample_value(
        "ai_tokens_total",
        {
            "backend": "test_backend",
            "model": "test_model",
            "token_type": "total",
        },
    )
    new_request = metrics.registry.get_sample_value(
        "ai_request_duration_seconds_count",
        {"backend": "test_backend", "model": "test_model", "status": "success"},
    )

    assert new_prompt == base_prompt + 10
    assert new_completion == base_completion + 20
    assert new_total == base_total + 30
    assert new_request == base_request + 1.0


@pytest.mark.asyncio
async def test_ai_call_instrumented_failure() -> None:
    metrics = get_metrics()
    base_request = (
        metrics.registry.get_sample_value(
            "ai_request_duration_seconds_count",
            {
                "backend": "test_backend_err",
                "model": "test_model",
                "status": "error",
            },
        )
        or 0.0
    )

    with pytest.raises(ValueError, match="simulated error"):
        async with ai_call_instrumented("test_backend_err", "test_model", logger):
            raise ValueError("simulated error")

    new_request = metrics.registry.get_sample_value(
        "ai_request_duration_seconds_count",
        {
            "backend": "test_backend_err",
            "model": "test_model",
            "status": "error",
        },
    )
    assert new_request == base_request + 1.0


@pytest.mark.asyncio
async def test_deepseek_metrics_integration() -> None:
    from bb_paxdata.infrastructure.ai.deepseek import DeepSeekClient

    client = DeepSeekClient(api_key="ds-key", model="deepseek-chat")
    metrics = get_metrics()

    base_prompt = (
        metrics.registry.get_sample_value(
            "ai_tokens_total",
            {
                "backend": "deepseek",
                "model": "deepseek-chat",
                "token_type": "prompt",
            },
        )
        or 0.0
    )
    base_completion = (
        metrics.registry.get_sample_value(
            "ai_tokens_total",
            {
                "backend": "deepseek",
                "model": "deepseek-chat",
                "token_type": "completion",
            },
        )
        or 0.0
    )

    mock_response_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"test": 1}',
                }
            }
        ],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 25,
            "total_tokens": 40,
        },
    }

    mock_post = AsyncMock()
    mock_post.return_value = Response(
        200,
        json=mock_response_data,
        request=Request("POST", "https://api.deepseek.com/chat/completions"),
    )
    client._client.post = mock_post

    result = await client.complete("Hello")
    assert result.success is True
    assert result.prompt_tokens == 15
    assert result.completion_tokens == 25
    assert result.tokens_used == 40

    new_prompt = metrics.registry.get_sample_value(
        "ai_tokens_total",
        {
            "backend": "deepseek",
            "model": "deepseek-chat",
            "token_type": "prompt",
        },
    )
    new_completion = metrics.registry.get_sample_value(
        "ai_tokens_total",
        {
            "backend": "deepseek",
            "model": "deepseek-chat",
            "token_type": "completion",
        },
    )

    assert new_prompt == base_prompt + 15
    assert new_completion == base_completion + 25
