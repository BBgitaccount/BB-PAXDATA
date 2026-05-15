"""Uncertainty scorer for AI analysis outputs using Monte Carlo consistency method."""

import asyncio
import json
import time
from collections import Counter
from typing import Any, Literal, cast

import structlog
from pydantic import BaseModel

from .consistency import ConsistencyCalculator

logger = structlog.get_logger(__name__)


class UncertaintyScore(BaseModel):
    """Uncertainty score for a single sentence."""

    sent_id: str
    overall_confidence: float  # 0.0 - 1.0
    field_scores: dict[str, float]
    consensus_map: dict[str, str]  # Most frequent values
    raw_outputs: list[Any]  # 3 AI outputs (debug)
    recommendation: Literal["ACCEPT", "REVIEW", "REJECT"]
    latency_ms: int


class UncertaintyScorer:
    """Measures AI output confidence using consistency-based approach."""

    def __init__(
        self, ai_backend: Any, weights: dict[str, float] | None = None
    ) -> None:
        self.ai_backend = ai_backend
        self.consistency_calc = ConsistencyCalculator()

        # Default weights from Faz 5 specification
        self.weights = weights or {
            "AI_Risk_Skoru": 0.30,
            "AI_Duygu_Skoru": 0.20,
            "AI_Cerceveleme": 0.15,
            "AI_Diplomatik_Ton": 0.15,
            "AI_Manipulasyon_Skor": 0.10,
            "other_textual": 0.10,
        }

        self.logger = structlog.get_logger(__name__)

    async def score_sentence(
        self, sent_id: str, source_text: str, context: dict[str, Any] | None = None
    ) -> UncertaintyScore:
        """
        Score uncertainty for a single sentence using 3 AI calls.

        Args:
            sent_id: Sentence identifier
            source_text: Original sentence text
            context: Additional context (speaker, panel, etc.)

        Returns:
            UncertaintyScore with confidence metrics
        """
        start_time = time.time()

        try:
            # Make 3 parallel AI calls with different temperatures
            temperatures = [0.3, 0.5, 0.7]

            tasks = []
            for temp in temperatures:
                task = self._call_ai_with_temperature(source_text, temp, context)
                tasks.append(task)

            # Wait for all calls to complete
            raw_outputs = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and parse valid outputs
            valid_outputs = []
            for i, output in enumerate(raw_outputs):
                if isinstance(output, Exception):
                    self.logger.error(f"AI call {i} failed: {output}")
                    continue

                try:
                    parsed_output = self._parse_ai_output(output)
                    if parsed_output:
                        valid_outputs.append(parsed_output)
                except Exception as e:
                    self.logger.error(f"Failed to parse AI output {i}: {e}")

            if len(valid_outputs) < 2:
                # Not enough valid outputs for consistency check
                return UncertaintyScore(
                    sent_id=sent_id,
                    overall_confidence=0.0,
                    field_scores={},
                    consensus_map={},
                    raw_outputs=[str(o) for o in raw_outputs],
                    recommendation="REJECT",
                    latency_ms=int((time.time() - start_time) * 1000),
                )

            # Calculate field-wise consistency scores
            field_scores = self._calculate_field_scores(valid_outputs)

            # Calculate overall weighted confidence
            overall_confidence = self._calculate_overall_confidence(field_scores)

            # Get consensus values
            consensus_map = self._get_consensus_values(valid_outputs)

            # Make recommendation
            recommendation = self._make_recommendation(overall_confidence, field_scores)

            latency_ms = int((time.time() - start_time) * 1000)

            return UncertaintyScore(
                sent_id=sent_id,
                overall_confidence=overall_confidence,
                field_scores=field_scores,
                consensus_map=consensus_map,
                raw_outputs=valid_outputs,
                recommendation=recommendation,
                latency_ms=latency_ms,
            )

        except Exception as e:
            self.logger.error(f"Error scoring uncertainty for {sent_id}: {e}")
            return UncertaintyScore(
                sent_id=sent_id,
                overall_confidence=0.0,
                field_scores={},
                consensus_map={},
                raw_outputs=[],
                recommendation="REJECT",
                latency_ms=int((time.time() - start_time) * 1000),
            )

    async def _call_ai_with_temperature(
        self, text: str, temperature: float, context: dict[str, Any] | None
    ) -> str:
        """Make AI call with specified temperature."""
        # This would call the actual AI backend
        # For now, return mock response
        await asyncio.sleep(0.1)  # Simulate API call

        # Mock response - replace with actual AI call
        mock_response = {
            "AI_Duygu_Skoru": -0.2 + temperature * 0.1,
            "AI_Risk_Skoru": 5 + int(temperature * 2),
            "AI_Potansiyel_Risk": "medium" if temperature < 0.6 else "high",
            "AI_Diplomatik_Ton": "defensive" if temperature < 0.5 else "assertive",
            "AI_Manipulasyon_Skor": 0.3 + temperature * 0.1,
            "AI_Cerceveleme": "security_frame",
            "AI_Birincil_Konu": "Güvenlik_Çatışma",
        }

        return json.dumps(mock_response)

    def _parse_ai_output(self, raw_output: Any) -> dict[str, Any] | None:
        """Parse AI output string to dictionary."""
        try:
            if isinstance(raw_output, str):
                return cast(dict[str, Any], json.loads(raw_output))
            elif isinstance(raw_output, dict):
                return cast(dict[str, Any], raw_output)
            else:
                return None
        except json.JSONDecodeError:
            return None

    def _calculate_field_scores(
        self, outputs: list[dict[str, Any]]
    ) -> dict[str, float]:
        """Calculate consistency scores for each field."""
        field_scores = {}

        # Get all fields present in outputs
        all_fields: set[str] = set()
        for output in outputs:
            all_fields.update(output.keys())

        for field in all_fields:
            field_values = [
                output.get(field) for output in outputs if output.get(field) is not None
            ]

            if len(field_values) < 2:
                field_scores[field] = 0.0
                continue

            # Calculate consistency based on field type
            if self._is_numeric_field(field):
                # Numeric field: use coefficient of variation
                consistency = self.consistency_calc.numeric_consistency(
                    [float(v) for v in field_values if v is not None]
                )
            elif self._is_categorical_field(field):
                # Categorical field: use consensus ratio
                consistency = self.consistency_calc.categorical_consensus(
                    [str(v) for v in field_values if v is not None]
                )
            else:
                # Text field: use Jaccard similarity or embedding similarity
                consistency = self.consistency_calc.textual_consistency(
                    [str(v) for v in field_values if v is not None]
                )

            field_scores[field] = consistency

        return field_scores

    def _calculate_overall_confidence(self, field_scores: dict[str, float]) -> float:
        """Calculate weighted overall confidence score."""
        weighted_sum = 0.0
        total_weight = 0.0

        for field, score in field_scores.items():
            weight = self._get_field_weight(field)
            weighted_sum += score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _get_consensus_values(self, outputs: list[dict[str, Any]]) -> dict[str, str]:
        """Get most frequent values for each field."""
        consensus_map = {}

        # Get all fields present in outputs
        all_fields: set[str] = set()
        for output in outputs:
            all_fields.update(output.keys())

        for field in all_fields:
            field_values = [
                str(output.get(field, ""))
                for output in outputs
                if output.get(field) is not None
            ]

            if field_values:
                # Get most frequent value
                counter = Counter(field_values)
                most_common = counter.most_common(1)[0][0]
                consensus_map[field] = most_common

        return consensus_map

    def _make_recommendation(
        self, overall_confidence: float, field_scores: dict[str, float]
    ) -> Literal["ACCEPT", "REVIEW", "REJECT"]:
        """Make recommendation based on confidence scores."""
        # Critical fields that must have high confidence
        critical_fields = ["AI_Risk_Skoru", "AI_Duygu_Skoru"]

        critical_confidence = min(
            field_scores.get(field, 0.0) for field in critical_fields
        )

        if overall_confidence >= 0.8 and critical_confidence >= 0.7:
            return "ACCEPT"
        elif overall_confidence >= 0.6 and critical_confidence >= 0.5:
            return "REVIEW"
        else:
            return "REJECT"

    def _is_numeric_field(self, field: str) -> bool:
        """Check if field contains numeric values."""
        numeric_fields = [
            "AI_Duygu_Skoru",
            "AI_Risk_Skoru",
            "AI_Manipulasyon_Skoru",
            "AI_Talep_Var",
        ]
        return field in numeric_fields

    def _is_categorical_field(self, field: str) -> bool:
        """Check if field contains categorical values."""
        categorical_fields = ["AI_Potansiyel_Risk", "AI_Diplomatik_Ton"]
        return field in categorical_fields

    def _get_field_weight(self, field: str) -> float:
        """Get weight for field based on predefined weights."""
        # Direct match
        if field in self.weights:
            return self.weights[field]

        # Textual fields
        if not self._is_numeric_field(field) and not self._is_categorical_field(field):
            return self.weights.get("other_textual", 0.1)

        # Default weight
        return 0.05

    async def score_batch(
        self, sentences: list[dict[str, Any]]
    ) -> list[UncertaintyScore]:
        """
        Score uncertainty for a batch of sentences.

        Args:
            sentences: List of sentence dictionaries with sent_id and text

        Returns:
            List of UncertaintyScore objects
        """
        tasks = []
        for sentence in sentences:
            task = self.score_sentence(
                sent_id=sentence["sent_id"],
                source_text=sentence["text"],
                context=sentence.get("context"),
            )
            tasks.append(task)

        # Process in parallel with concurrency limit
        semaphore = asyncio.Semaphore(5)  # Limit concurrent AI calls

        async def bounded_score(sentence: dict[str, Any]) -> UncertaintyScore:
            async with semaphore:
                return await self.score_sentence(
                    sent_id=sentence["sent_id"],
                    source_text=sentence["text"],
                    context=sentence.get("context"),
                )

        tasks = [bounded_score(sentence) for sentence in sentences]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Error scoring sentence {i}: {result}")
                continue
            valid_results.append(result)

        return [r for r in valid_results if isinstance(r, UncertaintyScore)]
