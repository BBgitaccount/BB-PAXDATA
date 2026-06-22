"""
AIAnomalyController — LLM-as-a-Judge semantik anomali denetçisi.

Deterministik CrossAnomalyService sonuçlarını semantik olarak
doğrular, false positive'leri filtreler ve derin semantik anomalileri
yakalar.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

from bb_paxdata.application.domain.models.anomaly import (
    AnomalyResult,
    AnomalyValidationDecision,
    AnomalyValidationResult,
)
from bb_paxdata.application.domain.models.sentence import Sentence
from bb_paxdata.infrastructure.ai.base import CompletionOptions

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.ai.base import AIClient
    from bb_paxdata.infrastructure.ai.recovery import RecoveryEngine

logger = structlog.get_logger(__name__)


class AIAnomalyController:
    """
    Dual-Gate Anomaly Engine'in AI (soft-logic) kapısı.

    Kullanım:
        controller = AIAnomalyController(ai_client=client)
        result = await controller.validate(
            sentence=sentence,
            deterministic_result=anomaly_result,
            context_sentences=last_5_sentences
        )
    """

    _PROMPT_ID = "anomaly_validation"
    _PROMPT_VERSION = "v1.0"

    def __init__(
        self,
        ai_client: AIClient,
        recovery_engine: RecoveryEngine,
        max_context_sentences: int = 5,
    ) -> None:
        self._client = ai_client
        self._recovery = recovery_engine
        self._max_ctx = max_context_sentences

    async def validate(
        self,
        sentence: Sentence,
        deterministic_result: AnomalyResult,
        context_sentences: list[Sentence],
    ) -> AnomalyValidationResult:
        """
        Ana denetim metodu. Deterministik sonucu LLM ile validate eder.
        Hata durumunda INCONCLUSIVE döner, pipeline'ı asla kesmez.
        """
        prompt = self._build_prompt(sentence, deterministic_result, context_sentences)

        try:
            options = CompletionOptions(temperature=0.1, max_tokens=512)
            completion_res = await self._client.complete(
                user_message=prompt,
                options=options,
            )
            raw_content = completion_res.content if completion_res.success else ""
            parsed = await asyncio.to_thread(self._recovery.recover, raw_content)
            data = parsed if isinstance(parsed, dict) else (parsed.data or {})
            return self._parse_response(data, raw_content)

        except Exception as exc:
            logger.warning(
                "AIAnomalyController failed, returning INCONCLUSIVE",
                extra={"sentence_id": sentence.id, "error": str(exc)},
            )
            # In a full implementation, we'd persist this to AIFailAnalysis
            # e.g., session.add(AIFailAnalysis(error=str(exc))) via a UoW
            return AnomalyValidationResult(
                decision=AnomalyValidationDecision.INCONCLUSIVE,
                coherence_score=0.5,
                reasoning="LLM validation failed; fallback to deterministic result.",
                detected_subtype=None,
                confidence=0.0,
                raw_llm_response="",
            )

    def _build_prompt(
        self,
        sentence: Sentence,
        det_result: AnomalyResult,
        context: list[Sentence],
    ) -> str:
        ctx_block = "\n".join(
            f"[{i + 1}] {s.text}" for i, s in enumerate(context[-self._max_ctx :])
        )

        # Guard in case det_result structure is different, though we matched it in anomaly.py
        if getattr(det_result, "has_anomaly", False):
            rules = [
                getattr(r, "value", str(r))
                for r in getattr(det_result, "triggered_rules", [])
            ]
            anomaly_block = (
                f"Triggered Rules: {rules}\n"
                f"Anomaly Score: {getattr(det_result, 'anomaly_score', 0):.3f}\n"
                f"Confidence: {getattr(det_result, 'confidence', 0):.3f}"
            )
        else:
            anomaly_block = "No deterministic anomaly detected."

        return f"""You are an expert in diplomatic discourse analysis acting as an anomaly validation judge.

## CONTEXT (last {self._max_ctx} sentences):
{ctx_block}

## SENTENCE UNDER ANALYSIS:
"{sentence.text}"

## DETERMINISTIC ANOMALY ENGINE RESULT:
{anomaly_block}

## YOUR TASK:
Analyze the sentence in its diplomatic context and validate or challenge the deterministic result.
Consider:
- Is this genuine contradiction or strategic irony/rhetoric?
- Does the speaker use diplomatic subtext that rules cannot capture?
- Are there hidden coercive signals or tone shifts the rules missed?

Respond ONLY with a valid JSON object:
{{
  "decision": "<CONFIRMED|DISMISSED|ESCALATED|AI_ONLY|INCONCLUSIVE>",
  "coherence_score": <0.0-1.0, where 1.0=fully coherent/no anomaly>,
  "reasoning": "<concise explanation in the same language as the sentence>",
  "detected_subtype": "<irony|rhetorical_strategy|coercive_signal|tone_drift|null>",
  "confidence": <0.0-1.0>
}}"""

    @staticmethod
    def _parse_response(parsed: dict[str, Any], raw: str) -> AnomalyValidationResult:
        try:
            decision = AnomalyValidationDecision(parsed.get("decision", "INCONCLUSIVE"))
        except ValueError:
            decision = AnomalyValidationDecision.INCONCLUSIVE

        return AnomalyValidationResult(
            decision=decision,
            coherence_score=float(parsed.get("coherence_score", 0.5)),
            reasoning=str(parsed.get("reasoning", "")),
            detected_subtype=parsed.get("detected_subtype"),
            confidence=float(parsed.get("confidence", 0.0)),
            raw_llm_response=raw,
        )
