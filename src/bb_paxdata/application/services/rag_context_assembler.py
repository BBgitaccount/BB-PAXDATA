# src/bb_paxdata/application/services/rag_context_assembler.py
from __future__ import annotations

from typing import Sequence

from bb_paxdata.application.domain.services.prompt_registry import PromptRegistry
from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    RetrievedContext,
)


class RAGContextAssembler:
    def __init__(self, prompt_registry: PromptRegistry) -> None:
        self._registry = prompt_registry

    async def build_prompt(
        self, query: str, contexts: Sequence[RetrievedContext]
    ) -> str:
        prompt_meta = await self._registry.get("rag_synthesis@v2.0")
        if not prompt_meta:
            raise ValueError("Prompt template rag_synthesis@v2.0 not registered.")

        # Deduplicate by sentence_id while preserving order
        seen: set[str] = set()
        unique_ctx: list[RetrievedContext] = []
        for c in contexts:
            if c.sentence_id not in seen:
                seen.add(c.sentence_id)
                unique_ctx.append(c)

        context_str = "\n".join(
            f"- [{c.speaker_name} ({c.country}) | panel:{c.panel_id}]: {c.text}"
            for c in unique_ctx
        )

        return prompt_meta.content.format(
            context=context_str,
            query=query,
            source_count=len(unique_ctx),
        )
