from __future__ import annotations

import os

# Inject mock OpenAI API key for testing environment (required by deepeval)
os.environ.setdefault("OPENAI_API_KEY", "mock-openai-api-key-for-testing")
