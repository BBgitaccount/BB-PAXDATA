"""FewShotInjector — injects gold‑standard human reviews into prompts.
"""

from __future__ import annotations

import logging
from typing import Any

from bb_paxdata.domain.models.human_review import HumanReview

logger = logging.getLogger(__name__)

_FEW_SHOT_TEMPLATE = """
## UZMAN ONAYLI REFERANS ÖRNEKLER (Few‑Shot Gold Standard)
{examples_block}

## ŞİMDİ SEN ANALİZ ET:
"""


class FewShotInjector:
    def __init__(self, uow_factory: Any, enabled: bool = True) -> None:
        self._uow_factory = uow_factory
        self._enabled = enabled

    async def inject(
        self, base_prompt: str, frame_hint: str | None = None, n_examples: int = 3
    ) -> str:
        if not self._enabled:
            return base_prompt
        try:
            async with self._uow_factory() as uow:
                examples = await uow.human_reviews.get_gold_standard_examples(
                    frame_type=frame_hint, limit=n_examples
                )
        except Exception as exc:
            logger.warning(
                "FewShotInjector DB error, skipping injection",
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
    def _format_example(idx: int, review: HumanReview) -> str:
        return (
            f"**Örnek {idx}:**\n"
            f"  - Metin: {review.sentence_text or 'N/A'}\n"
            f"  - Uzman Frame: {review.human_dominant_frame or 'N/A'}\n"
            f"  - Uzman Risk: {review.human_risk_level.value if review.human_risk_level else 'N/A'}\n"
            f"  - Uzman SBI: {review.human_sbi_score or 'N/A'}\n"
            f"  - Gerekçe: {review.disagreement_reason or '(Onaylı analiz)'}"
        )
