# src/bb_paxdata/application/services/dki_evaluator.py
from __future__ import annotations

import hashlib
import inspect
import json
import time
from typing import Any, Callable

import structlog
from bb_paxdata.application.domain.services.prompt_registry import PromptRegistry
from bb_paxdata.application.domain.services.protocols import AIAnalystProtocol
from bb_paxdata.application.domain.services.protocols.judge_protocols import (
    BaselineMetrics,
    JudgeProtocol,
    JudgeVerdict,
)
from bb_paxdata.infrastructure.db.model_evaluation import AuditEntry
from pydantic import ValidationError

logger = structlog.get_logger()


class DKIEvaluator(JudgeProtocol):
    PROMPT_VERSION = "dki_judge@v2.1"

    def __init__(
        self,
        ai_client: AIAnalystProtocol,
        prompt_registry: PromptRegistry,
        audit_session_factory: Callable[[], Any],
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        self._client = ai_client
        self._registry = prompt_registry
        self._audit_factory = audit_session_factory
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def evaluate(
        self,
        speaker_name: str,
        country: str,
        sentence_text: str,
        pipeline_sentiment: str,
        pipeline_risk_score: float,
        pipeline_frame: str,
        baseline: BaselineMetrics,
    ) -> JudgeVerdict:
        prompt_template = await self._registry.get(self.PROMPT_VERSION)
        if not prompt_template:
            raise ValueError(f"Prompt template {self.PROMPT_VERSION} not registered.")

        # Build deterministic prompt
        payload = {
            "speaker_name": speaker_name,
            "country": country,
            "sentence_text": sentence_text,
            "pipeline_sentiment": pipeline_sentiment,
            "pipeline_risk_score": pipeline_risk_score,
            "pipeline_frame": pipeline_frame,
            "historical_sentiment_avg": baseline.historical_sentiment_avg,
            "historical_risk_avg": baseline.historical_risk_avg,
            "historical_frame": baseline.historical_frame_mode,
        }
        prompt_text = prompt_template.content.format(**payload)
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:16]

        t0 = time.perf_counter()

        # Check signature dynamically
        sig = inspect.signature(self._client.analyze)
        kwargs: dict[str, Any] = {}
        if "temperature" in sig.parameters:
            kwargs["temperature"] = self._temperature
        if "max_tokens" in sig.parameters:
            kwargs["max_tokens"] = self._max_tokens
        if "response_format" in sig.parameters:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            raw_response = await self._client.analyze(prompt_text, **kwargs)
        except Exception as e:
            logger.error("judge_llm_failure", error=str(e), prompt_hash=prompt_hash)
            raise

        inference_time_ms = (time.perf_counter() - t0) * 1000
        response_text = raw_response.raw_output or raw_response.summary or "{}"
        response_hash = hashlib.sha256(response_text.encode()).hexdigest()[:16]

        # Parse & validate JSON response from raw_output
        try:
            # Strip markdown JSON block if present
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

            parsed = json.loads(cleaned_text)

            verdict = JudgeVerdict(
                semantic_shift_score=float(parsed.get("semantic_shift_score", 0.0)),
                is_consistent=bool(parsed.get("is_consistent", True)),
                calibration_drift=float(parsed.get("calibration_drift", 0.0)),
                reasoning=str(parsed.get("reasoning", "")),
                prompt_hash=prompt_hash,
                response_hash=response_hash,
                model_used=getattr(raw_response, "model_name", "unknown"),
                inference_time_ms=inference_time_ms,
            )
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(
                "judge_parse_failure",
                raw_output=response_text[:500],
                error=str(e),
            )
            # Graceful fallback verdict on parse error to prevent pipeline crash
            verdict = JudgeVerdict(
                semantic_shift_score=0.0,
                is_consistent=True,
                calibration_drift=0.0,
                reasoning=f"Parse failure: {e}",
                prompt_hash=prompt_hash,
                response_hash=response_hash,
                model_used=getattr(raw_response, "model_name", "unknown"),
                inference_time_ms=inference_time_ms,
            )

        # Async audit trail (WORM)
        await self._emit_audit(verdict, payload)

        logger.info(
            "judge_verdict",
            speaker=speaker_name,
            consistent=verdict.is_consistent,
            shift_score=verdict.semantic_shift_score,
            prompt_hash=prompt_hash,
        )
        return verdict

    async def _emit_audit(self, verdict: JudgeVerdict, payload: dict[str, Any]) -> None:
        entry = AuditEntry(
            action_type="LLM_JUDGE",
            entity_type="Sentence",
            details={
                "verdict": verdict.model_dump(),
                "input_payload_hash": hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest()[:16],
            },
        )
        async with self._audit_factory() as session:
            session.add(entry)
            await session.commit()
