# src/bb_paxdata/application/services/rag_service.py
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING

import structlog
from bb_paxdata.application.domain.services.prompt_registry import PromptRegistry
from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    DenseRetrieverProtocol,
    KeywordRetrieverProtocol,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSynthesisProtocol,
    RerankerProtocol,
    RetrievedContext,
)
from bb_paxdata.application.services.rag_context_assembler import RAGContextAssembler
from bb_paxdata.infrastructure.ai.rag_synthesis_adapter import (  # noqa: F401
    RAGSynthesisClient,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.db.repositories.analysis import AnalysisRepository

logger = structlog.get_logger()


class RAGService:
    def __init__(
        self,
        keyword_retriever: KeywordRetrieverProtocol,
        dense_retriever: DenseRetrieverProtocol,
        reranker: RerankerProtocol | None,
        synthesis_client: RAGSynthesisProtocol,
        prompt_registry: PromptRegistry,
        analysis_repository: AnalysisRepository | None = None,
        max_keyword_context: int = 20,
        max_dense_context: int = 20,
        enable_cache: bool = True,
    ) -> None:
        self._keyword = keyword_retriever
        self._dense = dense_retriever
        self._reranker = reranker
        self._synthesis = synthesis_client
        self._assembler = RAGContextAssembler(prompt_registry)
        self._analysis_repo = analysis_repository
        self._max_kw = max_keyword_context
        self._max_dense = max_dense_context
        self._enable_cache = enable_cache

    def _generate_cache_key(self, request: RAGQueryRequest) -> str:
        """Generate a unique cache key for RAG query based on request parameters."""
        cache_data = {
            "query": request.query,
            "panel_id_filter": request.panel_id_filter,
            "country_filters": sorted(request.country_filters or []),
            "speaker_filter": request.speaker_filter,
            "top_k_keyword": request.top_k_keyword,
            "top_k_dense": request.top_k_dense,
            "top_k_rerank": request.top_k_rerank,
            "temperature": request.temperature,
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()

    async def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        t0 = time.perf_counter()

        # Check cache if enabled and repository is available
        cache_key = self._generate_cache_key(request)
        if self._enable_cache and self._analysis_repo:
            cached_result = await self._analysis_repo.get_cache(
                cache_key, file_id=request.panel_id_filter
            )
            if cached_result:
                logger.info(
                    "rag_query_cache_hit",
                    cache_key=cache_key[:16],
                    query=request.query[:100],
                )
                # Deserialize cached response
                try:
                    cached_data = json.loads(cached_result.result_json)
                    return RAGQueryResponse(
                        query=request.query,
                        answer=cached_data.get("answer", ""),
                        sources=[
                            RetrievedContext(**ctx)
                            for ctx in cached_data.get("sources", [])
                        ],
                        latency_ms=(time.perf_counter() - t0) * 1000,
                        total_tokens=cached_data.get("total_tokens"),
                    )
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(
                        "rag_cache_deserialize_failed",
                        cache_key=cache_key[:16],
                        error=str(e),
                    )

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

        response = RAGQueryResponse(
            query=request.query,
            answer=answer if isinstance(answer, str) else "",
            sources=list(final_contexts),
            latency_ms=latency,
            total_tokens=None,  # populated by synthesis client if available
        )

        # Store in cache if enabled and repository is available
        if self._enable_cache and self._analysis_repo:
            try:
                cache_data = {
                    "answer": response.answer,
                    "sources": [ctx.model_dump() for ctx in response.sources],
                    "total_tokens": response.total_tokens,
                }
                await self._analysis_repo.set_cache(
                    cache_key=cache_key,
                    result_json=json.dumps(cache_data),
                    model_used="rag_synthesis",
                    backend_used="rag_pipeline",
                    file_id=request.panel_id_filter,
                )
                logger.info(
                    "rag_query_cached",
                    cache_key=cache_key[:16],
                    query=request.query[:100],
                )
            except Exception as e:
                logger.warning(
                    "rag_cache_store_failed",
                    cache_key=cache_key[:16],
                    error=str(e),
                )

        logger.info(
            "rag_query_complete",
            latency_ms=round(latency, 2),
            sources=len(final_contexts),
            stream=request.stream,
            cached=False,
        )

        return response

    async def stream(self, request: RAGQueryRequest) -> AsyncIterator[str]:
        """SSE-compatible streaming entrypoint.

        Note: Streaming responses are not cached due to their incremental nature.
        Use .query() for cached responses.
        """
        if not request.stream:
            raise ValueError("Use .query() for non-streaming requests.")

        # Streaming bypasses cache since responses are incremental
        logger.info(
            "rag_stream_start",
            query=request.query[:100],
            cache_bypassed=True,
        )

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

    async def store_rag_explanation(
        self,
        request: RAGQueryRequest,
        response: RAGQueryResponse,
        synthesis_explanation: str | None = None,
    ) -> None:
        """Store RAG query explanation in AIExplanationsORM.

        This is an optional feature for tracking and explaining RAG synthesis decisions.
        Note: AIExplanationsORM is primarily designed for sentence-level analysis,
        so we adapt it for RAG by using a special sent_id format.

        Args:
            request: The original RAG query request
            response: The RAG query response
            synthesis_explanation: Optional explanation of the synthesis process
        """
        if not self._analysis_repo:
            logger.warning("rag_explanation_store_failed: no analysis repository")
            return

        try:
            # Generate a unique sentence ID for this RAG query
            rag_sent_id = f"rag_query:{self._generate_cache_key(request)}"

            # Create explanation data
            # Note: AIExplanationsORM expects sentence-level fields, we adapt them for RAG
            risk_explanation = (
                f"RAG query processed with {len(response.sources)} sources retrieved"
            )
            sentiment_explanation = f"Query: {request.query}"
            executive_summary = response.answer[:500] if response.answer else ""
            token_attributions_json = json.dumps(
                {
                    "query": request.query,
                    "sources_count": len(response.sources),
                    "latency_ms": response.latency_ms,
                    "top_sources": [
                        {
                            "sentence_id": ctx.sentence_id,
                            "similarity_score": ctx.similarity_score,
                            "retrieval_source": ctx.retrieval_source,
                        }
                        for ctx in response.sources[:5]
                    ],
                }
            )

            # Store using the repository
            await self._analysis_repo.save_rag_explanation(
                sent_id=rag_sent_id,
                risk_explanation=risk_explanation,
                sentiment_explanation=sentiment_explanation,
                executive_summary=executive_summary,
                token_attributions_json=token_attributions_json,
                grammatical_explanation=synthesis_explanation,
            )

            logger.info(
                "rag_explanation_stored",
                rag_sent_id=rag_sent_id[:32],
                sources_count=len(response.sources),
                latency_ms=response.latency_ms,
            )

        except Exception as e:
            logger.warning(
                "rag_explanation_store_failed",
                error=str(e),
            )

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
