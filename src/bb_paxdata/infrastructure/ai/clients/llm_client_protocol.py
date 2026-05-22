from __future__ import annotations

from typing import Protocol


class LLMClientProtocol(Protocol):
    """Protocol for LLM clients used in PFA extraction pipeline."""

    async def generate(self, prompt: str, temperature: float = 0.0) -> str:
        """Generate text completion from a prompt asynchronously."""
        ...
