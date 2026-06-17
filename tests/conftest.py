from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from celery import Task

# Inject mock OpenAI API key for testing environment (required by deepeval)
os.environ.setdefault("OPENAI_API_KEY", "mock-openai-api-key-for-testing")

# Mock Celery delay method globally to prevent connection attempts to Broker (Redis)

Task.delay = MagicMock()


# Auto-use fixture to mock redis asyncio client globally in tests
@pytest.fixture(autouse=True)
def mock_redis_connection(monkeypatch):
    import redis.asyncio as aioredis

    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.is_allowed = AsyncMock(return_value=True)

    monkeypatch.setattr(aioredis.Redis, "from_url", MagicMock(return_value=mock_client))
