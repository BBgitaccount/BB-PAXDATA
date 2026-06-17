"""CalibrationService — computes inter‑rater agreement and persists reports.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from bb_paxdata.application.domain.models.calibration import CalibrationReport
from bb_paxdata.application.domain.models.human_review import (
    AgreementStatus,
    HumanReview,
)

logger = structlog.get_logger(__name__)

KAPPA_RELIABLE_THRESHOLD = 0.67
F1_ALERT_THRESHOLD = 0.70
DISAGREEMENT_RATE_ALERT = 0.30


class CalibrationService:
    def __init__(self, uow_factory: Any = None, metric: str | None = None) -> None:
        self._uow_factory = uow_factory
        self.metric = metric

    def apply_platt_scaling(self, raw_confidence: float) -> float:
        """Applies Platt scaling sigmoid function to calibrate confidence scores."""
        import math

        # Sigmoid: 1 / (1 + exp(- (A * x + B)))
        # Map 0.5 to ~0.5, 0.75 to ~0.73, etc. using A=4.0, B=-2.0
        val = 4.0 * raw_confidence - 2.0
        try:
            return 1.0 / (1.0 + math.exp(-val))
        except OverflowError:
            return 0.0 if val < 0 else 1.0

    async def run_weekly_calibration(
        self, prompt_version: str, days_back: int = 7
    ) -> CalibrationReport:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days_back)

        async with self._uow_factory() as uow:
            reviews = await uow.human_reviews.get_reviews_for_prompt(
                prompt_version=prompt_version, limit=500
            )

        if not reviews:
            logger.warning(
                "No reviews for calibration", extra={"prompt": prompt_version}
            )
            return self._empty_report(prompt_version, start, end)

        kappa_frame = self._cohens_kappa(
            [r.ai_dominant_frame for r in reviews],
            [r.human_dominant_frame for r in reviews],
        )
        kappa_risk = self._cohens_kappa(
            [r.ai_risk_level.value if r.ai_risk_level else None for r in reviews],
            [r.human_risk_level.value if r.human_risk_level else None for r in reviews],
        )
        f1_frame = self._macro_f1(
            [r.ai_dominant_frame for r in reviews],
            [r.human_dominant_frame for r in reviews],
        )
        f1_risk = self._macro_f1(
            [r.ai_risk_level.value if r.ai_risk_level else None for r in reviews],
            [r.human_risk_level.value if r.human_risk_level else None for r in reviews],
        )
        sbi_mae = self._mean_absolute_error(
            [r.ai_sbi_score for r in reviews], [r.human_sbi_score for r in reviews]
        )

        disagreements = [
            r for r in reviews if r.agreement_status == AgreementStatus.DISAGREED
        ]
        patterns = self._extract_patterns(disagreements)

        requires_prompt = (f1_frame is not None and f1_frame < F1_ALERT_THRESHOLD) or (
            f1_risk is not None and f1_risk < F1_ALERT_THRESHOLD
        )
        requires_weight = sbi_mae is not None and sbi_mae > 10.0

        alert = None
        if requires_prompt:
            alert = f"F1 below threshold (frame={f1_frame if f1_frame is not None else 0.0:.2f}, risk={f1_risk if f1_risk is not None else 0.0:.2f}). Prompt update needed."
        elif requires_weight:
            alert = f"SBI MAE high ({sbi_mae if sbi_mae is not None else 0.0:.1f}). Review weight parameters."

        report = CalibrationReport(
            prompt_version=prompt_version,
            evaluation_period_start=start,
            evaluation_period_end=end,
            cohens_kappa_frame=kappa_frame,
            cohens_kappa_risk=kappa_risk,
            ai_human_f1_frame=f1_frame,
            ai_human_f1_risk=f1_risk,
            sbi_mae=sbi_mae,
            total_reviews=len(reviews),
            total_disagreements=len(disagreements),
            top_disagreement_patterns=patterns,
            requires_prompt_update=requires_prompt,
            requires_weight_update=requires_weight,
            alert_message=alert,
        )

        async with self._uow_factory() as uow:
            await uow.calibration.save(report)
            await uow.commit()

        if alert:
            logger.warning(
                "Calibration alert", extra={"alert": alert, "prompt": prompt_version}
            )
        return report

    @staticmethod
    def _cohens_kappa(
        rater_a: list[str | None], rater_b: list[str | None]
    ) -> float | None:
        pairs = [
            (a, b) for a, b in zip(rater_a, rater_b) if a is not None and b is not None
        ]
        if len(pairs) < 2:
            return None
        n = len(pairs)
        po = sum(1 for a, b in pairs if a == b) / n
        labels = set(a for a, _ in pairs) | set(b for _, b in pairs)
        count_a = Counter(a for a, _ in pairs)
        count_b = Counter(b for _, b in pairs)
        pe = sum((count_a[lbl] / n) * (count_b[lbl] / n) for lbl in labels)
        return 1.0 if pe == 1.0 else (po - pe) / (1.0 - pe)

    @staticmethod
    def _macro_f1(predicted: list[str | None], true: list[str | None]) -> float | None:
        pairs = [
            (p, t) for p, t in zip(predicted, true) if p is not None and t is not None
        ]
        if not pairs:
            return None
        labels = set(t for _, t in pairs)
        f1_scores = []
        for label in labels:
            tp = sum(1 for p, t in pairs if p == label and t == label)
            fp = sum(1 for p, t in pairs if p == label and t != label)
            fn = sum(1 for p, t in pairs if p != label and t == label)
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                (2 * precision * recall / (precision + recall))
                if (precision + recall) > 0
                else 0.0
            )
            f1_scores.append(f1)
        return sum(f1_scores) / len(f1_scores)

    @staticmethod
    def _mean_absolute_error(
        ai_scores: list[float | None], human_scores: list[float | None]
    ) -> float | None:
        pairs = [
            (a, h)
            for a, h in zip(ai_scores, human_scores)
            if a is not None and h is not None
        ]
        if not pairs:
            return None
        return sum(abs(a - h) for a, h in pairs) / len(pairs)

    @staticmethod
    def _extract_patterns(disagreements: list[HumanReview]) -> list[str]:
        reasons = [
            r.disagreement_reason for r in disagreements if r.disagreement_reason
        ]
        seen = []
        for r in reasons:
            if r not in seen:
                seen.append(r)
            if len(seen) >= 5:
                break
        return seen

    @staticmethod
    def _empty_report(
        prompt_version: str, start: datetime, end: datetime
    ) -> CalibrationReport:
        return CalibrationReport(
            prompt_version=prompt_version,
            evaluation_period_start=start,
            evaluation_period_end=end,
            total_reviews=0,
        )
