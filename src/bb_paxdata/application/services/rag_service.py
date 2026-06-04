# src/bb_paxdata/application/services/rag_service.py
from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Sequence

import structlog
from bb_paxdata.application.services.rag_context_assembler import RAGContextAssembler
from bb_paxdata.domain.services.prompt_registry import PromptRegistry
from bb_paxdata.domain.services.protocols import AIAnalystProtocol
from bb_paxdata.domain.services.protocols.rag_protocols import (
    DenseRetrieverProtocol,
    KeywordRetrieverProtocol,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSynthesisProtocol,
    RerankerProtocol,
    RetrievedContext,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = structlog.get_logger()


class RAGSynthesisClient(RAGSynthesisProtocol):
    def __init__(self, ai_analyst: AIAnalystProtocol) -> None:
        self._ai = ai_analyst

    async def synthesize(
        self, query: str, contexts: Sequence[RetrievedContext], stream: bool
    ) -> str | AsyncIterator[str]:
        # query is the pre-constructed prompt
        if stream:

            async def token_generator() -> AsyncIterator[str]:
                res = await self._ai.analyze(query)
                output = res.raw_output or ""
                # chunk output to simulate streaming
                chunk_size = max(1, len(output) // 20)
                for i in range(0, len(output), chunk_size):
                    yield output[i : i + chunk_size]
                    await asyncio.sleep(0.01)

            return token_generator()
        else:
            res = await self._ai.analyze(query)
            return res.raw_output or ""


class RAGService:
    def __init__(
        self,
        keyword_retriever: KeywordRetrieverProtocol,
        dense_retriever: DenseRetrieverProtocol,
        reranker: RerankerProtocol | None,
        synthesis_client: RAGSynthesisProtocol,
        prompt_registry: PromptRegistry,
        max_keyword_context: int = 20,
        max_dense_context: int = 20,
    ) -> None:
        self._keyword = keyword_retriever
        self._dense = dense_retriever
        self._reranker = reranker
        self._synthesis = synthesis_client
        self._assembler = RAGContextAssembler(prompt_registry)
        self._max_kw = max_keyword_context
        self._max_dense = max_dense_context

    async def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        t0 = time.perf_counter()

        # Parallel retrieval
        keyword_task = self._keyword.search(request)
        dense_task = self._dense.search(request)
        kw_results, dense_results = await asyncio.gather(keyword_task, dense_task)

        # Fusion: RRF (Reciprocal Rank Fusion) for initial ranking
        fused = self._reciprocal_rank_fusion(kw_results, dense_results, k=60)

        # Rerank if available
        final_contexts: Sequence[RetrievedContext] = fused
        if self._reranker and request.top_k_rerank > 0:
            final_contexts = await self._reranker.rerank(
                request.query, fused, request.top_k_rerank
            )

        # Build prompt
        prompt = await self._assembler.build_prompt(request.query, final_contexts)

        # Synthesis with circuit-breaker-friendly retry
        answer = await self._synthesize_with_retry(prompt, request.stream)

        latency = (time.perf_counter() - t0) * 1000

        logger.info(
            "rag_query_complete",
            latency_ms=round(latency, 2),
            sources=len(final_contexts),
            stream=request.stream,
        )

        return RAGQueryResponse(
            query=request.query,
            answer=answer if isinstance(answer, str) else "",
            sources=list(final_contexts),
            latency_ms=latency,
            total_tokens=None,  # populated by synthesis client if available
        )

    async def stream(self, request: RAGQueryRequest) -> AsyncIterator[str]:
        """SSE-compatible streaming entrypoint."""
        if not request.stream:
            raise ValueError("Use .query() for non-streaming requests.")

        kw_results, dense_results = await asyncio.gather(
            self._keyword.search(request),
            self._dense.search(request),
        )
        fused = self._reciprocal_rank_fusion(kw_results, dense_results, k=60)
        final_contexts = fused
        if self._reranker:
            final_contexts = await self._reranker.rerank(
                request.query, fused, request.top_k_rerank
            )

        prompt = await self._assembler.build_prompt(request.query, final_contexts)

        # Resolve the generator/stream correctly
        stream_generator = await self._synthesize_with_retry(prompt, stream=True)
        if isinstance(stream_generator, str):
            yield stream_generator
        else:
            async for token in stream_generator:
                yield token

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    async def _synthesize_with_retry(
        self, prompt: str, stream: bool
    ) -> str | AsyncIterator[str]:
        return await self._synthesis.synthesize(prompt, [], stream=stream)  # type: ignore[no-any-return]

    def _reciprocal_rank_fusion(
        self,
        keyword_results: Sequence[RetrievedContext],
        dense_results: Sequence[RetrievedContext],
        k: int = 60,
    ) -> Sequence[RetrievedContext]:
        scores: dict[str, float] = {}
        meta: dict[str, RetrievedContext] = {}

        for rank, ctx in enumerate(keyword_results, start=1):
            scores[ctx.sentence_id] = scores.get(ctx.sentence_id, 0.0) + 1.0 / (
                k + rank
            )
            meta[ctx.sentence_id] = ctx

        for rank, ctx in enumerate(dense_results, start=1):
            scores[ctx.sentence_id] = scores.get(ctx.sentence_id, 0.0) + 1.0 / (
                k + rank
            )
            if ctx.sentence_id not in meta:
                meta[ctx.sentence_id] = ctx

        sorted_ids = sorted(scores.keys(), key=lambda sid: scores[sid], reverse=True)
        return [meta[sid] for sid in sorted_ids[:20]]
