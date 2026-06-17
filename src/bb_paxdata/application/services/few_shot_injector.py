# src/bb_paxdata/application/services/few_shot_injector.py
from __future__ import annotations

from typing import Any

import structlog
from bb_paxdata.application.services.dynamic_few_shot_optimizer import (
    VectorSimilaritySelector,
)

logger = structlog.get_logger(__name__)

_FEW_SHOT_TEMPLATE = """
## UZMAN ONAYLI REFERANS ÖRNEKLER (Few‑Shot Gold Standard)
{examples_block}

## ŞİMDİ SEN ANALİZ ET:
"""


class FewShotInjector:
    def __init__(
        self,
        uow_factory: Any | None = None,
        selector: VectorSimilaritySelector | None = None,
        enabled: bool = True,
        max_examples: int = 3,
    ) -> None:
        self._selector = selector
        self._uow_factory = uow_factory
        self._enabled = enabled
        self._max_examples = max_examples

    async def inject(
        self,
        base_prompt: str,
        frame_hint: str | None = None,
        n_examples: int | None = None,
    ) -> str:
        if not self._enabled:
            return base_prompt

        limit = n_examples if n_examples is not None else self._max_examples

        # Extract target sentence text from base_prompt
        target_text = None
        for marker in ["Metin:", "Text:"]:
            if marker in base_prompt:
                target_text = base_prompt.rsplit(marker, maxsplit=1)[-1].strip()
                break
        if not target_text:
            target_text = base_prompt

        examples = []
        if self._selector:
            try:
                examples = await self._selector.select(
                    target_text=target_text,
                    n_examples=limit,
                )
            except Exception as exc:
                logger.warning(
                    f"DynamicFewShotSelector error, skipping/falling back: {exc}"
                )

        # Fallback to get_gold_standard_examples from human review repository if selector is None
        if not examples and self._uow_factory:
            try:
                async with self._uow_factory() as uow:
                    examples = await uow.human_reviews.get_gold_standard_examples(
                        frame_type=frame_hint, limit=limit
                    )
            except Exception as exc:
                logger.warning(
                    "FewShotInjector DB fallback error, skipping injection",
                    extra={"error": str(exc)},
                )
                return base_prompt

        if not examples:
            return base_prompt

        examples_block = "\n\n".join(
            self._format_example(i + 1, ex) for i, ex in enumerate(examples)
        )
        injection = _FEW_SHOT_TEMPLATE.format(examples_block=examples_block)
        return base_prompt.rstrip() + "\n\n" + injection

    @staticmethod
    def _format_example(idx: int, review: Any) -> str:
        sentence_text = getattr(review, "sentence_text", "N/A")

        assigned_sentiment = getattr(review, "assigned_sentiment", None)
        if assigned_sentiment is None:
            assigned_sentiment = str(getattr(review, "human_sentiment_score", "N/A"))

        assigned_frame = getattr(
            review, "assigned_frame", getattr(review, "human_dominant_frame", "N/A")
        )

        assigned_risk_level = getattr(review, "human_risk_level", None)
        if assigned_risk_level:
            assigned_risk = assigned_risk_level.value
        else:
            assigned_risk = str(
                getattr(
                    review,
                    "assigned_risk_score",
                    getattr(review, "human_sbi_score", "N/A"),
                )
            )

        reason = getattr(review, "disagreement_reason", "(Onaylı analiz)")
        if not reason:
            reason = "(Onaylı analiz)"

        return (
            f"**Örnek {idx}:**\n"
            f"  - Metin: {sentence_text}\n"
            f"  - Uzman Frame: {assigned_frame}\n"
            f"  - Uzman Sentiment: {assigned_sentiment}\n"
            f"  - Uzman Risk: {assigned_risk}\n"
            f"  - Gerekçe: {reason}"
        )
