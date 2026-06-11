"""RAGSynthesisClient — adapter that bridges AIAnalystProtocol → RAGSynthesisProtocol.

Infrastructure layer: wraps a concrete AI client with the RAG synthesis interface.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from bb_paxdata.application.domain.services.protocols import AIAnalystProtocol
from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    RAGSynthesisProtocol,
    RetrievedContext,
)


class RAGSynthesisClient(RAGSynthesisProtocol):
    """Wraps AIAnalystProtocol to produce RAG synthesis outputs."""

    def __init__(self, ai_analyst: AIAnalystProtocol) -> None:
        self._ai = ai_analyst

    async def synthesize(
        self, query: str, contexts: Sequence[RetrievedContext], stream: bool
    ) -> str | AsyncIterator[str]:
        if stream:

            async def token_generator() -> AsyncIterator[str]:
                res = await self._ai.analyze(query)
                output = res.raw_output or ""
                chunk_size = max(1, len(output) // 20)
                for i in range(0, len(output), chunk_size):
                    yield output[i : i + chunk_size]
                    await asyncio.sleep(0.01)

            return token_generator()
        else:
            res = await self._ai.analyze(query)
            return res.raw_output or ""
