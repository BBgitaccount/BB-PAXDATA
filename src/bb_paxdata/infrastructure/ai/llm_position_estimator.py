import asyncio
import hashlib
from typing import Any, Protocol

import numpy as np
import structlog

from bb_paxdata.domain.models.dki import LLMPositionEstimate, PositionCalibration
from bb_paxdata.infrastructure.ai.prompt_registry import PromptRegistry
from bb_paxdata.infrastructure.ai.recovery import RecoveryEngine

logger = structlog.get_logger()


class AIClient(Protocol):
    """Protocol for LLM clients (Anthropic, Gemini, etc.)."""

    async def generate(self, prompt: str, temperature: float = 0.0) -> str: ...


class CambridgeCoreLLMPositionEstimator:
    """Cambridge Core (2026) LLM positioning implementation.

    Methodology:
    - Split text into sentences (using a simple split or external tokenizer).
    - Rate each sentence on 0-100 scale via LLM.
    - Average sentence scores for text-level position.
    """

    PROMPT_ID = "llm_position"
    PROMPT_VERSION = "1.0"

    def __init__(
        self,
        client: AIClient,
        prompt_registry: PromptRegistry,
        recovery_engine: RecoveryEngine,
        max_concurrent: int = 10,
    ) -> None:
        self._client = client
        self._registry = prompt_registry
        self._recovery = recovery_engine
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._logger = logger.bind(service="llm_position")

    async def estimate_position(
        self,
        text: str,
        policy_dimension: str,
        schema_enforce: bool = True,
    ) -> LLMPositionEstimate:
        """Deterministic LLM-based position estimation."""

        # 1. Fetch prompt from registry
        prompt_version = await self._registry.get(self.PROMPT_ID, self.PROMPT_VERSION)
        if not prompt_version:
            # Fallback if not registered (should be registered in Phase 8 setup)
            template = self._get_default_template()
            prompt_version = await self._registry.register(
                self.PROMPT_ID, template, academic_ref="cambridge_core_2026"
            )

        # 2. Sentencize text (simple split for now, assuming pre-cleaned)
        # In a real scenario, use spaCy or the provided sentences in Analysis.
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if not sentences:
            sentences = [text]

        # 3. Gather sentence scores
        tasks = [
            self._score_sentence(s, policy_dimension, prompt_version.content)
            for s in sentences
        ]
        results = await asyncio.gather(*tasks)

        sentence_scores = [r for r in results if r is not None]
        if not sentence_scores:
            self._logger.error("No sentence scores were successfully generated")
            raise ValueError("Failed to estimate position for any sentences")

        # 4. Average scores
        positions = [s["position"] for s in sentence_scores]
        avg_pos = sum(positions) / len(positions)
        std_dev = float(np.std(positions)) if len(positions) > 1 else 0.0

        # 5. Build Result
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        return LLMPositionEstimate(
            text_hash=text_hash,
            policy_dimension=policy_dimension,
            average_position=avg_pos,
            sentence_scores=sentence_scores,
            std_deviation=std_dev,
            prompt_version=prompt_version.version_id,
            prompt_sha256=prompt_version.content_hash,
            model_name=getattr(self._client, "model_name", "unknown"),
            temperature=0.0,
        )

    async def _score_sentence(
        self, sentence: str, dimension: str, template: str
    ) -> dict[str, Any] | None:
        """Score a single sentence with retry and recovery."""
        prompt = template.replace("{{policy_dimension}}", dimension).replace(
            "{{sentence}}", sentence
        )

        async with self._semaphore:
            try:
                response = await self._client.generate(prompt, temperature=0.0)
                recovery_result = self._recovery.recover(
                    response,
                    default_schema={
                        "position": 50,
                        "confidence": 0.0,
                        "rationale": "recovery fallback",
                    },
                )

                if recovery_result.success and recovery_result.data:
                    data: dict[str, Any] = recovery_result.data
                    # Ensure numeric types
                    data["position"] = int(data.get("position", 50))
                    data["confidence"] = float(data.get("confidence", 0.0))
                    data["sentence"] = sentence
                    return data
            except Exception as e:
                self._logger.warning(
                    "Failed to score sentence",
                    error=str(e),
                    sentence_preview=sentence[:50],
                )
                return None
        return None

    async def calibrate_against_wordfish(
        self,
        llm_estimates: list[LLMPositionEstimate],
        wordfish_thetas: list[float],
    ) -> PositionCalibration:
        """Compute calibration drift between LLM and Wordfish positions."""
        if len(llm_estimates) != len(wordfish_thetas) or not llm_estimates:
            return PositionCalibration(
                pearson_r=0.0,
                mean_absolute_error=0.0,
                drift_detected=False,
                sample_size=len(llm_estimates),
            )

        llm_pos = np.array([e.average_position for e in llm_estimates])
        wf_pos = np.array(wordfish_thetas)

        # Normalize wordfish to 0-100 for comparison if needed,
        # or just compute correlation.
        # Wordfish θ is usually centered around 0.
        # Let's assume Wordfish is [-3, 3] and map to [0, 100].
        wf_norm = (wf_pos - (-3)) / (3 - (-3)) * 100
        wf_norm = np.clip(wf_norm, 0, 100)

        pearson_r = float(np.corrcoef(llm_pos, wf_norm)[0, 1])
        mae = float(np.mean(np.abs(llm_pos - wf_norm)))

        drift_detected = mae > 15.0 or pearson_r < 0.5

        return PositionCalibration(
            pearson_r=pearson_r,
            mean_absolute_error=mae,
            drift_detected=drift_detected,
            sample_size=len(llm_estimates),
        )

    def _get_default_template(self) -> str:
        return """You are an expert political text analyst performing policy position estimation.

TASK: Rate the following diplomatic statement on a continuous scale of 0 to 100.

SCALE DEFINITION:
- 0 = Maximally opposed, dovish, conciliatory, status-quo challenging
- 50 = Neutral, balanced, purely descriptive
- 100 = Maximally supportive, hawkish, confrontational, status-quo defending

POLICY DIMENSION: {{policy_dimension}}

STATEMENT: "{{sentence}}"

INSTRUCTIONS:
1. Consider only the explicit policy position conveyed in this sentence.
2. Ignore diplomatic politeness formulas unless they encode substantive position.
3. Respond ONLY in valid JSON matching the schema: {"position": int, "confidence": float, "rationale": str}
4. Do not include markdown code blocks or explanatory text outside JSON.

OUTPUT:"""
