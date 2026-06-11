"""
Presupposition Verifier Service
LLM-backed verification layer for presupposition candidates.
Routes through existing AIClientFactory and BatchProcessor infrastructure.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import structlog

from bb_paxdata.application.domain.models.presupposition import (
    Presupposition,
    TriggerType,
    VerificationMethod,
)
from bb_paxdata.infrastructure.ai.base import (
    AIClient,
    CompletionOptions,
)
from bb_paxdata.infrastructure.cache.base import CacheBackend

logger = structlog.get_logger(__name__)


@dataclass
class PresuppositionCandidate:
    """Candidate presupposition for verification."""

    trigger_word: str
    trigger_type: TriggerType
    presupposed_content: str
    confidence: float
    segment_id: str
    speaker: str
    segment_text: str
    timestamp: float | None = None


class PresuppositionVerifier:
    """
    LLM-backed verification layer for presupposition candidates.
    Routes through existing AIClientFactory and CacheBackend infrastructure.

    NOTE: Uses individual JSON-mode calls per candidate instead of batch processing
    to avoid the known AnthropicClient JSON prefill bug. Batch processing can be
    added in Phase 1.3 once the prefill bug is resolved.
    """

    _PROMPT_KEY = "presupposition_verification_v1"

    def __init__(
        self,
        ai_client: AIClient,
        cache: CacheBackend,
        use_cache: bool = True,
    ) -> None:
        """
        Initialize the verifier.

        Args:
            ai_client: AI client instance from AIClientFactory
            cache: Cache backend for verification results
            use_cache: Whether to use caching
        """
        self._client = ai_client
        self._cache = cache
        self._use_cache = use_cache

    async def verify_candidate(
        self,
        candidate: PresuppositionCandidate,
    ) -> Presupposition | None:
        """
        Verify a single presupposition candidate via LLM.

        Args:
            candidate: Candidate to verify

        Returns:
            Presupposition if verified, None if rejected as false positive
        """
        cache_key = self._make_cache_key(candidate)

        # Check cache
        if self._use_cache:
            cached_result = await self._cache.get(cache_key)
            if cached_result is not None:
                logger.debug(
                    "Cache hit for presupposition verification", cache_key=cache_key
                )
                return Presupposition(**cached_result)

        # Build prompt
        prompt = self._build_prompt(candidate)

        # Call LLM with JSON mode (NOT prefill due to known bug)
        options = CompletionOptions(json_mode=True)
        result = await self._client.complete(prompt, options)

        if not result.success or not result.parsed:
            logger.warning(
                "LLM verification failed",
                segment_id=candidate.segment_id,
                trigger=candidate.trigger_word,
                error=result.error,
            )
            # On failure, return the candidate with rule-based verification
            return self._create_presupposition(
                candidate,
                verification_method=VerificationMethod.RULE,
                llm_confidence=None,
            )

        # Parse response
        parsed = result.parsed
        is_valid = parsed.get("is_valid", False)
        llm_confidence = parsed.get("confidence", 0.0)
        refined_content = parsed.get("refined_content", candidate.presupposed_content)

        if not is_valid or llm_confidence < 0.5:
            logger.debug(
                "LLM rejected presupposition candidate",
                segment_id=candidate.segment_id,
                trigger=candidate.trigger_word,
                confidence=llm_confidence,
            )
            return None  # Filter as false positive

        # Create verified presupposition
        presupposition = self._create_presupposition(
            candidate,
            verification_method=VerificationMethod.LLM,
            llm_confidence=llm_confidence,
            presupposed_content=refined_content,
        )

        # Cache result
        if self._use_cache:
            await self._cache.set(
                cache_key,
                presupposition.model_dump(),
                ttl=None,  # No TTL as per FINDING m-03
            )

        return presupposition

    async def verify_batch(
        self,
        candidates: list[PresuppositionCandidate],
    ) -> list[Presupposition]:
        """
        Verify multiple candidates in parallel.

        Args:
            candidates: List of candidates to verify

        Returns:
            List of verified presuppositions (rejected candidates filtered out)
        """
        import asyncio

        tasks = [self.verify_candidate(c) for c in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        verified = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error(
                    "Verification exception",
                    segment_id=candidates[i].segment_id,
                    error=str(result),
                )
                # Fall back to rule-based
                verified.append(
                    self._create_presupposition(
                        candidates[i],
                        verification_method=VerificationMethod.RULE,
                        llm_confidence=None,
                    )
                )
            elif result is not None:
                verified.append(result)

        return verified

    def _make_cache_key(self, candidate: PresuppositionCandidate) -> str:
        """
        Generate cache key for a candidate.
        Key: sha256(trigger_word|trigger_type|segment_id)[:16]
        """
        raw = f"{candidate.trigger_word}|{candidate.trigger_type.value}|{candidate.segment_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _build_prompt(self, candidate: PresuppositionCandidate) -> str:
        """
        Build verification prompt for a candidate.

        Uses JSON mode response format to avoid the prefill bug.
        """
        prompt = f"""You are an expert in linguistic presupposition analysis (Lewis 1979, Beaver & Geurts 2014).

Analyze the following diplomatic utterance and determine if the presupposition candidate is valid.

## UTTERANCE:
Speaker: {candidate.speaker}
Text: "{candidate.segment_text}"

## PRESUPPOSITION CANDIDATE:
Trigger word: "{candidate.trigger_word}"
Trigger type: {candidate.trigger_type.value}
Presupposed content: "{candidate.presupposed_content}"
Rule-based confidence: {candidate.confidence:.2f}

## YOUR TASK:
Determine if this is a genuine presupposition (content taken for granted by the speaker) or a false positive.
Consider:
- Does the trigger word actually induce a presupposition in this context?
- Is the presupposed content indeed taken for granted?
- Is this a genuine commitment or merely rhetorical?

Respond ONLY with valid JSON:
{{
  "is_valid": <boolean>,
  "confidence": <float 0.0-1.0>,
  "refined_content": "<string - refined presupposed content if valid, otherwise null>",
  "reasoning": "<brief explanation>"
}}"""
        return prompt

    def _create_presupposition(
        self,
        candidate: PresuppositionCandidate,
        verification_method: VerificationMethod,
        llm_confidence: float | None,
        presupposed_content: str | None = None,
    ) -> Presupposition:
        """
        Create a Presupposition from a candidate.
        """
        return Presupposition(
            trigger_word=candidate.trigger_word,
            trigger_type=candidate.trigger_type,
            presupposed_content=presupposed_content or candidate.presupposed_content,
            confidence=candidate.confidence,
            segment_id=candidate.segment_id,
            speaker=candidate.speaker,
            timestamp=candidate.timestamp,
            verification_method=verification_method,
            llm_confidence=llm_confidence,
        )
