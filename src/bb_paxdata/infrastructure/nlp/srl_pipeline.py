"""
Production-Grade Semantic Role Labeling Pipeline

Features:
- Thread-safe lazy initialization
- LRU caching with TTL
- Circuit breaker pattern for fault tolerance
- Automatic fallback to alternative models
- Comprehensive error handling and logging
- Batch processing support
- Performance metrics collection
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field

import structlog
import torch
from transformers import TokenClassificationPipeline, pipeline

from bb_paxdata.application.domain.models.srl import (
    SRLDocumentResult,
    SRLFrame,
    SRLSpan,
)
from bb_paxdata.infrastructure.nlp.srl_config import get_srl_config

# Configure module-level logger
logger = structlog.get_logger(__name__)


@dataclass
class CircuitBreakerState:
    """
    Circuit breaker implementation for fault tolerance.

    States:
    - CLOSED: Normal operation, requests flow through
    - OPEN: Failing, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered
    """

    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self) -> None:
        """Record successful operation."""
        self.success_count += 1
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit breaker transitioned to CLOSED state")

    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        config = get_srl_config()

        if self.state == "HALF_OPEN":
            self.state = "OPEN"
            logger.warning("Circuit breaker re-opened during HALF_OPEN test")
        elif (
            self.failure_count
            >= config.circuit_breaker_window * config.circuit_breaker_threshold
        ):
            self.state = "OPEN"
            logger.error(
                f"Circuit breaker OPENED: failure rate exceeded threshold "
                f"({self.failure_count}/{config.circuit_breaker_window})"
            )

    def allow_request(self) -> bool:
        """Check if request should be allowed through."""
        config = get_srl_config()

        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            # Check if cooldown period elapsed
            cooldown = config.retry_backoff_base ** min(config.max_retries, 5)
            if time.time() - self.last_failure_time > cooldown:
                self.state = "HALF_OPEN"
                self.failure_count = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN for testing")
                return True
            return False
        elif self.state == "HALF_OPEN":
            # Allow limited traffic to test recovery
            return True

        return False


@dataclass
class LRUCacheWithTTL:
    """
    Thread-safe LRU cache with time-to-live expiration.
    """

    cache: OrderedDict = field(default_factory=OrderedDict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    max_size: int = 10000
    ttl_seconds: float = 86400.0  # 24 hours

    def get(self, key: str) -> list[SRLFrame] | None:
        """Retrieve item if exists and not expired."""
        with self.lock:
            if key not in self.cache:
                return None

            value, timestamp = self.cache[key]

            # Check expiration
            if time.time() - timestamp > self.ttl_seconds:
                del self.cache[key]
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return value

    def put(self, key: str, value: list[SRLFrame]) -> None:
        """Store item in cache with eviction policy."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
            elif len(self.cache) >= self.max_size:
                # Evict oldest (first) item
                self.cache.popitem(last=False)

            self.cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear all cached items."""
        with self.lock:
            self.cache.clear()

    @property
    def size(self) -> int:
        """Return current cache size."""
        with self.lock:
            return len(self.cache)


@dataclass
class PerformanceMetrics:
    """Collect and aggregate performance metrics."""

    total_requests: int = 0
    total_cache_hits: int = 0
    total_failures: int = 0
    total_latency_ms: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record_request(self, latency_ms: float, cache_hit: bool, success: bool) -> None:
        """Record a single request metric."""
        with self.lock:
            self.total_requests += 1
            self.total_latency_ms += latency_ms
            if cache_hit:
                self.total_cache_hits += 1
            if not success:
                self.total_failures += 1

    @property
    def cache_hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_cache_hits / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return (self.total_requests - self.total_failures) / self.total_requests

    def reset(self) -> None:
        """Reset all metrics."""
        with self.lock:
            self.total_requests = 0
            self.total_cache_hits = 0
            self.total_failures = 0
            self.total_latency_ms = 0.0


class SRLPipeline:
    """
    Thread-safe, production-grade SRL extraction pipeline.

    Usage:
        >>> pipeline = SRLPipeline.get_instance()
        >>> result = pipeline.extract_from_text("Turkey rejected the proposal.")
        >>> print(result.frames[0].to_triplet())
        ('Turkey', 'rejected', 'the proposal')
    """

    _instance: SRLPipeline | None = None
    _lock: threading.Lock = threading.Lock()
    _init_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> SRLPipeline:
        """Singleton pattern with double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize pipeline lazily on first use."""
        if getattr(self, "_initialized", False):
            return

        with self._init_lock:
            if getattr(self, "_initialized", False):
                return

            self.config = get_srl_config()
            self._pipeline: TokenClassificationPipeline | None = None
            self._model_loaded: bool = False
            self._load_lock: threading.Lock = threading.Lock()

            # Initialize subsystems
            self.circuit_breaker = CircuitBreakerState()
            self.cache = LRUCacheWithTTL(
                max_size=self.config.cache_max_size,
                ttl_seconds=self.config.cache_ttl_seconds,
            )
            self.metrics = PerformanceMetrics()

            self._initialized = True
            logger.info("SRLPipeline initialized (model lazy-loaded)")

    @classmethod
    def get_instance(cls) -> SRLPipeline:
        """Factory method for accessing singleton."""
        return cls()

    @contextmanager
    def _acquire_pipeline(self):
        """
        Context manager for thread-safe pipeline access.
        Ensures model is loaded before use.
        """
        if not self._model_loaded:
            with self._load_lock:
                if not self._model_loaded:
                    self._load_model()

        yield self._pipeline

    def _load_model(self, model_name: str | None = None) -> None:
        """
        Load transformer model with error handling and fallback.

        Args:
            model_name: Specific model to load (uses config default if None)
        """
        target_model = model_name or self.config.model_name
        models_to_try = [target_model, *self.config.alternative_models]

        for model_id in models_to_try:
            try:
                logger.info(
                    f"Loading SRL model: {model_id} "
                    "(first run will download ~400 MB; subsequent runs use local cache)"
                )

                # Determine device and dtype
                device = self._resolve_device()
                torch_dtype = self._resolve_torch_dtype()

                # Load pipeline with optimizations.
                # aggregation_strategy='simple' merges BIO spans (B-ARG0 + I-ARG0 -> ARG0)
                # local_files_only=False allows first-time download then caches in HF_HOME
                self._pipeline = pipeline(
                    task="token-classification",
                    model=model_id,
                    device=device if device != "cpu" else -1,  # HF uses -1 for CPU
                    torch_dtype=torch_dtype,
                    aggregation_strategy="simple",
                )

                # Enable quantization if requested
                if self.config.use_quantization and hasattr(
                    self._pipeline.model, "quantize"
                ):
                    logger.info("Applying INT8 quantization to SRL model")
                    self._pipeline.model.quantize(bits=8)  # type: ignore

                self._model_loaded = True
                self.config.model_name = model_id  # Update active model

                logger.info(
                    f"SRL model loaded successfully: {model_id} | "
                    f"device={self.config.device}"
                )
                return

            except Exception as e:
                logger.warning(f"Failed to load model {model_id}: {e!s}")
                continue

        raise RuntimeError(f"All SRL models failed to load. Tried: {models_to_try}")

    def _resolve_device(self) -> int | str:
        """Map config device string to HuggingFace format."""
        device_map = {"cpu": -1, "cuda": 0, "mps": "mps"}
        return device_map.get(self.config.device, -1)

    def _resolve_torch_dtype(self) -> torch.dtype:
        """Map config dtype string to PyTorch dtype."""
        dtype_map = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }
        return dtype_map.get(self.config.torch_dtype, torch.float32)

    def extract_from_text(
        self, text: str, use_cache: bool = True, retry_on_failure: bool = True
    ) -> SRLDocumentResult:
        """
        Extract SRL frames from input text with full fault tolerance.

        Args:
            text: Input sentence/document text
            use_cache: Whether to check/use prediction cache
            retry_on_failure: Whether to retry on transient errors

        Returns:
            SRLDocumentResult containing extracted frames and metadata

        Raises:
            ValueError: If text is empty or invalid
            RuntimeError: If circuit breaker is open or all retries exhausted
        """
        # Input validation
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")

        text = text.strip()
        start_time = time.perf_counter()
        cache_hit = False
        success = False

        try:
            # Check circuit breaker
            if not self.circuit_breaker.allow_request():
                logger.warning("Request blocked: circuit breaker is OPEN")
                raise RuntimeError(
                    "SRL service unavailable (circuit breaker open). "
                    "Please retry later."
                )

            # Cache lookup
            cache_key = self._generate_cache_key(text)
            if use_cache and self.config.enable_cache:
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    cache_hit = True
                    success = True
                    latency = (time.perf_counter() - start_time) * 1000
                    self.metrics.record_request(latency, cache_hit, success)

                    logger.debug(f"Cache hit for text (len={len(text)})")
                    return SRLDocumentResult(
                        frames=cached_result,
                        total_sentences_processed=1,
                        total_frames_extracted=len(cached_result),
                        processing_time_ms=latency,
                    )

            # Actual inference with retry logic
            frames = self._extract_with_retry(text, retry_on_failure)

            # Store in cache
            if use_cache and self.config.enable_cache:
                self.cache.put(cache_key, frames)

            success = True
            self.circuit_breaker.record_success()

            latency = (time.perf_counter() - start_time) * 1000
            result = SRLDocumentResult(
                frames=frames,
                total_sentences_processed=text.count(".") + 1,
                total_frames_extracted=len(frames),
                processing_time_ms=latency,
            )

            self.metrics.record_request(latency, cache_hit, success)
            logger.debug(
                f"SRL extraction completed: {len(frames)} frames in {latency:.2f}ms"
            )

            return result

        except Exception as e:
            self.circuit_breaker.record_failure()
            success = False
            latency = (time.perf_counter() - start_time) * 1000
            self.metrics.record_request(latency, cache_hit, success)

            logger.error(f"SRL extraction failed: {e!s}")
            raise

    def _extract_with_retry(self, text: str, retry_enabled: bool) -> list[SRLFrame]:
        """
        Execute extraction with exponential backoff retry.

        Args:
            text: Input text
            retry_enabled: Enable/disable retry mechanism

        Returns:
            List of extracted SRL frames
        """
        last_exception = None

        for attempt in range(self.config.max_retries if retry_enabled else 1):
            try:
                with self._acquire_pipeline() as pipe:
                    raw_predictions = pipe(text)
                    return self._parse_predictions(raw_predictions, text)

            except Exception as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    wait_time = self.config.retry_backoff_base**attempt
                    logger.warning(
                        f"Retry {attempt + 1}/{self.config.max_retries} after "
                        f"{wait_time:.1f}s: {e!s}"
                    )
                    time.sleep(wait_time)

        raise RuntimeError(
            f"SRL extraction failed after {self.config.max_retries} attempts: "
            f"{last_exception!s}"
        )

    @staticmethod
    def _normalize_label(raw_label: str) -> str:
        """
        Normalize BIO-prefixed labels to clean role names.

        Examples::

            "B-ARG0" -> "ARG0"
            "I-ARG1" -> "ARG1"
            "B-V"    -> "V"
            "ARG0"   -> "ARG0"   (already clean, no-op)
        """
        if raw_label.startswith(("B-", "I-", "E-", "S-")):
            return raw_label[2:]
        return raw_label

    def _parse_predictions(
        self, raw_predictions: list[dict], original_text: str
    ) -> list[SRLFrame]:
        """
        Parse HuggingFace token classification output into structured SRL frames.

        Handles:
        - BIO tagging scheme (Begin-Inside-Outside); B-/I- prefixes are stripped
          by ``_normalize_label`` so the code works regardless of whether
          ``aggregation_strategy='simple'`` already collapsed spans.
        - Verb-centric frame grouping
        - Character offset alignment
        - Confidence filtering
        """
        frames: list[SRLFrame] = []
        if not isinstance(raw_predictions, list):
            raw_predictions = [raw_predictions]

        def _get_group(entity: dict) -> str:
            """Return the normalised label regardless of output format."""
            raw = entity.get("entity_group") or entity.get("entity") or ""
            return self._normalize_label(raw)

        # Group predictions by verb predicate
        verbs = [p for p in raw_predictions if _get_group(p) == "V"]

        for verb_pred in verbs:
            verb_text = verb_pred["word"].strip().lower()
            verb_confidence = verb_pred.get("score", 1.0)

            # Skip low-confidence verbs
            if verb_confidence < self.config.min_confidence_threshold:
                continue

            # Initialize frame data
            frame_data: dict = {
                "verb": verb_text,
                "arg0": None,
                "arg1": None,
                "arg2": None,
                "argm_mod": None,
                "argm_neg": False,
                "argm_tmp": None,
                "argm_cau": None,
                "argm_loc": None,
                "frame_confidence": verb_confidence,
            }

            # Map all argument entities to this frame.
            # Simple heuristic: each argument role is assigned once (first occurrence).
            for entity in raw_predictions:
                group = _get_group(entity)
                if group == "V":
                    continue

                try:
                    span = SRLSpan(
                        text=entity["word"],
                        start_char=entity["start"],
                        end_char=entity["end"],
                    )

                    if group == "ARG0" and frame_data["arg0"] is None:
                        frame_data["arg0"] = span
                    elif group == "ARG1" and frame_data["arg1"] is None:
                        frame_data["arg1"] = span
                    elif group == "ARG2" and frame_data["arg2"] is None:
                        frame_data["arg2"] = span
                    elif group == "ARGM-MOD":
                        frame_data["argm_mod"] = entity["word"].lower()
                    elif group == "ARGM-NEG":
                        frame_data["argm_neg"] = True
                    elif group == "ARGM-TMP" and frame_data["argm_tmp"] is None:
                        frame_data["argm_tmp"] = span
                    elif group == "ARGM-CAU" and frame_data["argm_cau"] is None:
                        frame_data["argm_cau"] = span
                    elif group == "ARGM-LOC" and frame_data["argm_loc"] is None:
                        frame_data["argm_loc"] = span

                except Exception as e:
                    logger.debug(f"Skipping malformed entity: {e}")
                    continue

            # Create validated frame
            try:
                frame = SRLFrame(**frame_data)
                frames.append(frame)
            except Exception as e:
                logger.warning(f"Failed to construct SRL frame: {e}")
                continue

        return frames

    def _generate_cache_key(self, text: str) -> str:
        """
        Generate deterministic cache key from text.
        Uses hash for memory efficiency.
        """
        import hashlib

        normalized = " ".join(text.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def extract_batch(
        self, texts: list[str], max_workers: int = 4
    ) -> list[SRLDocumentResult]:
        """
        Batch process multiple texts with optional parallelism.

        Args:
            texts: List of input texts
            max_workers: Maximum concurrent extractions

        Returns:
            List of SRLDocumentResult in same order as input
        """
        if not texts:
            return []

        results: list[SRLDocumentResult] = []

        # Sequential processing for now
        for text in texts:
            try:
                result = self.extract_from_text(text)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch item failed: {e}")
                results.append(SRLDocumentResult(frames=[]))

        return results

    def health_check(self) -> dict:
        """
        Return pipeline health status and metrics.

        Returns:
            Dictionary with status, metrics, and configuration info
        """
        return {
            "status": "healthy" if self._model_loaded else "initializing",
            "model_loaded": self._model_loaded,
            "active_model": self.config.model_name,
            "device": self.config.device,
            "circuit_breaker_state": self.circuit_breaker.state,
            "cache_stats": {
                "size": self.cache.size,
                "max_size": self.cache.max_size,
                "ttl_hours": self.cache.ttl_seconds / 3600,
            },
            "performance_metrics": {
                "total_requests": self.metrics.total_requests,
                "cache_hit_rate": f"{self.metrics.cache_hit_rate:.2%}",
                "avg_latency_ms": f"{self.metrics.avg_latency_ms:.2f}",
                "success_rate": f"{self.metrics.success_rate:.2%}",
            },
            "config": {
                "batch_size": self.config.batch_size,
                "min_confidence": self.config.min_confidence_threshold,
                "quantization": self.config.use_quantization,
            },
        }

    def clear_cache(self) -> None:
        """Manually clear prediction cache."""
        self.cache.clear()
        logger.info("SRL prediction cache cleared")

    def reset_circuit_breaker(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        self.circuit_breaker.state = "CLOSED"
        self.circuit_breaker.failure_count = 0
        logger.info("Circuit breaker manually reset")


# Convenience function for quick access
def get_srl_pipeline() -> SRLPipeline:
    """Get global SRLPipeline singleton instance."""
    return SRLPipeline.get_instance()
