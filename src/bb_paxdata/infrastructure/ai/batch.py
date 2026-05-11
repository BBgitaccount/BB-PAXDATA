from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from bb_paxdata.infrastructure.ai.base import (
    AIClient,
    CompletionOptions,
    CompletionResult,
)
from bb_paxdata.infrastructure.ai.recovery import RecoveryEngine
from bb_paxdata.infrastructure.cache import CacheBackend, DiskCacheBackend
from bb_paxdata.infrastructure.observability.metrics import get_metrics

logger = structlog.get_logger(__name__)


@dataclass
class BatchItem:
    """Single item in a batch processing request."""

    item_id: str  # sent_id
    payload: str  # sentence text
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result for a single batch item."""

    item_id: str
    success: bool
    parsed: dict[str, Any] | None
    content: str
    backend: str
    model: str
    latency_ms: int
    error: str | None = None
    from_cache: bool = False
    from_fallback: bool = False  # batch parse fail → individual retry


@dataclass
class BatchStats:
    """Statistics for batch processing."""

    total: int = 0
    success: int = 0
    failed: int = 0
    from_cache: int = 0
    fallback_triggered: int = 0
    total_tokens: int = 0
    total_latency_ms: int = 0


class BatchProcessor:
    """Processor for batch AI requests with smart fallback and retry logic."""

    def __init__(
        self,
        client: AIClient,
        batch_size: int = 5,  # AIanalyst BATCH_SIZE = 5
        max_workers: int = 3,  # AIanalyst MAX_WORKERS = 3
        max_retries: int = 3,  # AIanalyst MAX_RETRIES = 3
        use_cache: bool = True,
        options: CompletionOptions | None = None,
        cache_backend: CacheBackend | None = None,
        recovery_engine: RecoveryEngine | None = None,
    ) -> None:
        self._client = client
        self._batch_size = batch_size
        self._max_workers = max_workers
        self._max_retries = max_retries
        self._use_cache = use_cache
        self._options = options or CompletionOptions()
        self._cache = cache_backend or DiskCacheBackend()
        self._recovery = recovery_engine or RecoveryEngine()

    async def process(
        self,
        items: list[BatchItem],
        build_prompt: Callable[[list[BatchItem]], str],
    ) -> tuple[list[BatchResult], BatchStats]:
        """
        Process a batch of items with smart fallback.

        Args:
            items: List of items to process
            build_prompt: Function to build batch prompt from items

        Returns:
            Tuple of (results, stats)
        """
        stats = BatchStats(total=len(items))
        all_results: list[BatchResult] = []

        # Split items into chunks
        chunks = [
            items[i : i + self._batch_size]
            for i in range(0, len(items), self._batch_size)
        ]

        # Process chunks with semaphore
        semaphore = asyncio.Semaphore(self._max_workers)

        async def process_chunk(chunk: list[BatchItem]) -> list[BatchResult]:
            async with semaphore:
                return await self._process_chunk(chunk, build_prompt, stats)

        # Process all chunks
        chunk_results = await asyncio.gather(
            *[process_chunk(chunk) for chunk in chunks], return_exceptions=False
        )

        # Flatten results
        for chunk_result in chunk_results:
            all_results.extend(chunk_result)

        return all_results, stats

    async def _process_chunk(
        self,
        items: list[BatchItem],
        build_prompt: Callable[[list[BatchItem]], str],
        stats: BatchStats,
    ) -> list[BatchResult]:
        """Process a single chunk of items."""
        results: list[BatchResult] = []

        # 1. Cache check
        cache_results, uncached_items = await self._check_cache(items)
        results.extend(cache_results)
        stats.from_cache += len(cache_results)

        if not uncached_items:
            return results

        # 2. Try batch processing
        batch_result = await self._try_batch(uncached_items, build_prompt, stats)

        if batch_result:
            # Batch succeeded
            results.extend(batch_result)
        else:
            # 3. Fallback to individual processing
            stats.fallback_triggered += len(uncached_items)
            individual_results = await self._fallback_individual(uncached_items, stats)
            results.extend(individual_results)

        return results

    async def _check_cache(
        self, items: list[BatchItem]
    ) -> tuple[list[BatchResult], list[BatchItem]]:
        """Check cache for items."""
        cached_results: list[BatchResult] = []
        uncached_items: list[BatchItem] = []

        for item in items:
            cache_key = self._cache.make_key(item.payload)
            if self._use_cache:
                cached_result = await self._cache.get(cache_key)
                if cached_result:
                    cached_result.from_cache = True
                    cached_results.append(cached_result)
                else:
                    uncached_items.append(item)
            else:
                uncached_items.append(item)

        return cached_results, uncached_items

    async def _try_batch(
        self,
        items: list[BatchItem],
        build_prompt: Callable[[list[BatchItem]], str],
        stats: BatchStats,
    ) -> list[BatchResult] | None:
        """Try to process items as a batch."""
        try:
            # Build batch prompt
            batch_prompt = build_prompt(items)

            # Get completion with retry
            completion = await self._complete_with_retry(batch_prompt)

            if not completion.success or not completion.content:
                logger.warning(
                    "Batch completion failed or returned no content",
                    success=completion.success,
                    has_content=bool(completion.content),
                    error=completion.error,
                )

                # [FAZ3-METRIC]
                try:
                    reason = (
                        "timeout"
                        if "timeout" in str(completion.error).lower()
                        else "error"
                    )
                    get_metrics().record_batch_fallback(
                        backend=self._client.backend_name,
                        reason=reason,
                    )
                except Exception:
                    pass

                return None

            # Use RecoveryEngine to parse JSON response
            recovery_result = self._recovery.recover(completion.content)
            if not recovery_result.success:
                logger.warning(
                    "RecoveryEngine failed to parse batch response",
                    error=recovery_result.error,
                    level_used=recovery_result.level_used,
                )

                # [FAZ3-METRIC]
                try:
                    get_metrics().record_batch_fallback(
                        backend=self._client.backend_name,
                        reason="json_error",
                    )
                except Exception:
                    pass

                return None

            # Update completion with parsed data
            completion.parsed = recovery_result.data

            # Map batch response to individual items
            results = self._map_batch_response(items, completion)

            # Update stats
            for _ in results:
                stats.success += 1
                stats.total_tokens += completion.tokens_used // len(
                    items
                )  # Approximate
                stats.total_latency_ms += completion.latency_ms // len(
                    items
                )  # Approximate

            # Cache results
            if self._use_cache:
                for item, result in zip(items, results, strict=False):
                    cache_key = self._cache.make_key(item.payload)
                    await self._cache.set(cache_key, result, ttl=86400)

            return results

        except Exception as e:
            logger.error("Batch processing failed", error=str(e))

            # [FAZ3-METRIC]
            try:
                reason = "timeout" if "timeout" in str(e).lower() else "error"
                get_metrics().record_batch_fallback(
                    backend=self._client.backend_name,
                    reason=reason,
                )
            except Exception:
                pass

            return None

    async def _fallback_individual(
        self,
        items: list[BatchItem],
        stats: BatchStats,
    ) -> list[BatchResult]:
        """Fallback to individual processing for failed batch."""
        results: list[BatchResult] = []

        for item in items:
            try:
                completion = await self._complete_with_retry(item.payload)

                if completion.success and completion.content:
                    # Use RecoveryEngine to parse JSON response
                    recovery_result = self._recovery.recover(completion.content)

                    result = BatchResult(
                        item_id=item.item_id,
                        success=recovery_result.success,
                        parsed=(
                            recovery_result.data if recovery_result.success else None
                        ),
                        content=completion.content,
                        backend=completion.backend,
                        model=completion.model,
                        latency_ms=completion.latency_ms,
                        from_fallback=True,
                        error=(
                            recovery_result.error
                            if not recovery_result.success
                            else None
                        ),
                    )

                    if recovery_result.success:
                        stats.success += 1
                        stats.total_tokens += completion.tokens_used
                        stats.total_latency_ms += completion.latency_ms

                        # Cache result
                        if self._use_cache:
                            cache_key = self._cache.make_key(item.payload)
                            await self._cache.set(cache_key, result, ttl=86400)
                    else:
                        stats.failed += 1
                else:
                    result = BatchResult(
                        item_id=item.item_id,
                        success=False,
                        parsed=None,
                        content=completion.content or "",
                        backend=self._client.backend_name,
                        model=self._client.model_name,
                        latency_ms=completion.latency_ms,
                        error=completion.error,
                        from_fallback=True,
                    )
                    stats.failed += 1

                results.append(result)

            except Exception as e:
                logger.error(
                    "Individual fallback failed", item_id=item.item_id, error=str(e)
                )
                result = BatchResult(
                    item_id=item.item_id,
                    success=False,
                    parsed=None,
                    content="",
                    backend=self._client.backend_name,
                    model=self._client.model_name,
                    latency_ms=0,
                    error=str(e),
                    from_fallback=True,
                )
                stats.failed += 1
                results.append(result)

        return results

    async def _complete_with_retry(self, message: str) -> CompletionResult:
        """Complete with exponential backoff retry."""
        for attempt in range(self._max_retries):
            try:
                result = await self._client.complete(message, self._options)
                if result.success:
                    return result

                # If not success and not last attempt, wait and retry
                if attempt < self._max_retries - 1:
                    wait_time = 2**attempt  # 2s, 4s, 8s
                    logger.warning(
                        "Completion failed, retrying",
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        error=result.error,
                    )
                    await asyncio.sleep(wait_time)

            except Exception as e:
                if attempt < self._max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        "Completion exception, retrying",
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        error=str(e),
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Last attempt, return failure
                    return CompletionResult(
                        content="",
                        parsed=None,
                        backend=self._client.backend_name,
                        model=self._client.model_name,
                        tokens_used=0,
                        latency_ms=0,
                        success=False,
                        error=str(e),
                    )

        # All retries failed
        return CompletionResult(
            content="",
            parsed=None,
            backend=self._client.backend_name,
            model=self._client.model_name,
            tokens_used=0,
            latency_ms=0,
            success=False,
            error="All retries failed",
        )

    def _map_batch_response(
        self,
        items: list[BatchItem],
        completion: CompletionResult,
    ) -> list[BatchResult]:
        """Map batch response to individual items."""
        results: list[BatchResult] = []

        if not completion.parsed:
            # No parsed data, create failure results
            for item in items:
                results.append(
                    BatchResult(
                        item_id=item.item_id,
                        success=False,
                        parsed=None,
                        content="",
                        backend=completion.backend,
                        model=completion.model,
                        latency_ms=completion.latency_ms,
                        error="No parsed data in batch response",
                    )
                )
            return results

        # Try different response formats
        parsed = completion.parsed

        # Format 1: {"results": [{"sent_id": "...", ...}, ...]}
        if "results" in parsed and isinstance(parsed["results"], list):
            results_dict = {str(r.get("sent_id", "")): r for r in parsed["results"]}
            for item in items:
                item_data = results_dict.get(item.item_id)
                if item_data:
                    results.append(
                        BatchResult(
                            item_id=item.item_id,
                            success=True,
                            parsed=item_data,
                            content=json.dumps(item_data),
                            backend=completion.backend,
                            model=completion.model,
                            latency_ms=completion.latency_ms,
                        )
                    )
                else:
                    results.append(
                        BatchResult(
                            item_id=item.item_id,
                            success=False,
                            parsed=None,
                            content="",
                            backend=completion.backend,
                            model=completion.model,
                            latency_ms=completion.latency_ms,
                            error=f"Item {item.item_id} not found in batch response",
                        )
                    )
            return results

        # Format 2: [{"sent_id": "...", ...}, ...] - list of results
        if isinstance(parsed, list):
            results_dict = {str(r.get("sent_id", "")): r for r in parsed}
            for item in items:
                item_data = results_dict.get(item.item_id)
                if item_data:
                    results.append(
                        BatchResult(
                            item_id=item.item_id,
                            success=True,
                            parsed=item_data,
                            content=json.dumps(item_data),
                            backend=completion.backend,
                            model=completion.model,
                            latency_ms=completion.latency_ms,
                        )
                    )
                else:
                    # Fallback: use index order
                    index = items.index(item)
                    if index < len(parsed):
                        item_data = parsed[index]
                        results.append(
                            BatchResult(
                                item_id=item.item_id,
                                success=True,
                                parsed=item_data,
                                content=json.dumps(item_data),
                                backend=completion.backend,
                                model=completion.model,
                                latency_ms=completion.latency_ms,
                            )
                        )
                    else:
                        results.append(
                            BatchResult(
                                item_id=item.item_id,
                                success=False,
                                parsed=None,
                                content="",
                                backend=completion.backend,
                                model=completion.model,
                                latency_ms=completion.latency_ms,
                                error=(
                                    f"Item {item.item_id} not found in batch response"
                                ),
                            )
                        )
            return results

        # Unknown format, create failure results
        for item in items:
            results.append(
                BatchResult(
                    item_id=item.item_id,
                    success=False,
                    parsed=None,
                    content="",
                    backend=completion.backend,
                    model=completion.model,
                    latency_ms=completion.latency_ms,
                    error="Unknown batch response format",
                )
            )

        return results
