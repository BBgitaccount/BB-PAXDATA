from unittest.mock import AsyncMock, MagicMock

import pytest
from bb_paxdata.infrastructure.ai.base import CompletionOptions
from bb_paxdata.infrastructure.ai.deepseek import DeepSeekClient
from httpx import Request, Response


@pytest.mark.asyncio
async def test_deepseek_client_complete_success() -> None:
    """Test that DeepSeekClient completes messages successfully on a valid response."""
    client = DeepSeekClient(api_key="ds-key", model="deepseek-chat")

    mock_response_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"sentiment_score": 0.5, "sentiment_label": "positive"}',
                }
            }
        ],
        "usage": {"total_tokens": 42},
    }

    # Mock httpx AsyncClient.post
    mock_post = AsyncMock()
    mock_request = Request("POST", "https://api.deepseek.com/chat/completions")
    mock_post.return_value = Response(
        200, json=mock_response_data, request=mock_request
    )
    client._client.post = mock_post

    options = CompletionOptions(json_mode=True)
    result = await client.complete("Hello", options=options)

    assert result.success is True
    assert result.backend == "deepseek"
    assert result.model == "deepseek-chat"
    assert result.tokens_used == 42
    assert result.parsed == {"sentiment_score": 0.5, "sentiment_label": "positive"}
    assert result.content == '{"sentiment_score": 0.5, "sentiment_label": "positive"}'

    # Verify post arguments
    assert mock_post.called
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.deepseek.com/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer ds-key"


@pytest.mark.asyncio
async def test_deepseek_client_complete_failure() -> None:
    """Test that DeepSeekClient handles network failures gracefully."""
    client = DeepSeekClient(api_key="ds-key", model="deepseek-chat")

    # Mock post to raise HTTPStatusError
    mock_post = AsyncMock()
    mock_response = Response(
        500, request=Request("POST", "https://api.deepseek.com/chat/completions")
    )
    mock_post.return_value = mock_response
    client._client.post = mock_post

    result = await client.complete("Hello")

    assert result.success is False
    assert result.tokens_used == 0
    assert result.content == ""


@pytest.mark.asyncio
async def test_deepseek_client_health_check() -> None:
    """Test the health check functionality of DeepSeekClient."""
    client = DeepSeekClient(api_key="ds-key", model="deepseek-chat")

    # Mock success (200 OK)
    mock_post = AsyncMock()
    mock_post.return_value = Response(200)
    client._client.post = mock_post

    assert await client.health_check() is True

    # Mock failure (400 Bad Request)
    mock_post.return_value = Response(400)
    assert await client.health_check() is False


def test_deepseek_factory_integration() -> None:
    """Test that AIClientFactory can create DeepSeekClient and configure it correctly."""
    from bb_paxdata.infrastructure.ai.deepseek import DeepSeekClient
    from bb_paxdata.infrastructure.ai.factory import AIClientFactory

    # Test create with model=None uses default model
    client = AIClientFactory.create(backend="deepseek", api_key="ds-key")
    assert isinstance(client, DeepSeekClient)
    assert client.model_name == "deepseek-chat"

    # Test create with custom model
    client_custom = AIClientFactory.create(
        backend="deepseek", api_key="ds-key", model="deepseek-reasoner"
    )
    assert isinstance(client_custom, DeepSeekClient)
    assert client_custom.model_name == "deepseek-reasoner"

    # Test create fails if API key is missing
    with pytest.raises(ValueError, match="API key is required for DeepSeek backend"):
        AIClientFactory.create(backend="deepseek", api_key="")

    # Test from_settings
    mock_settings = MagicMock()
    mock_settings.ai_backend = "deepseek"
    mock_settings.ai_model = "deepseek-chat"
    mock_settings.deepseek_api_key = "ds-settings-key"

    client_settings = AIClientFactory.from_settings(mock_settings)
    assert isinstance(client_settings, DeepSeekClient)
    assert client_settings._api_key == "ds-settings-key"
    assert client_settings.model_name == "deepseek-chat"
