"""SubmitHumanReviewUseCase — submits a reviewer's correction/confirmation of an AI analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from bb_paxdata.application.domain.models.human_review import (
    AgreementStatus,
    HumanReview,
    RiskLevel,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SubmitHumanReviewCommand:
    analysis_id: str
    reviewer_id: str
    human_frame: str | None = None
    human_risk: str | None = None  # LOW, MED, HIGH, CRITICAL
    human_sbi: float | None = None
    human_sentiment: float | None = None
    disagreement_reason: str | None = None
    review_duration_seconds: int | None = None


class SubmitHumanReviewUseCase:
    def __init__(self, uow_factory: Any) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: SubmitHumanReviewCommand) -> HumanReview:
        async with self._uow_factory() as uow:
            # 1. Load the AI sentence analysis to extract reference AI scores
            analysis = await uow.analysis.get_sentence_analysis(command.analysis_id)
            if not analysis:
                # If not found directly, try to load by sent_id/id
                logger.warning(
                    "Sentence analysis not found in repository, creating review with fallback AI references",
                    extra={"analysis_id": command.analysis_id},
                )
                ai_sentiment_score = None
                ai_risk_level = None
                ai_dominant_frame = None
                ai_sbi_score = None
            else:
                ai_sentiment_score = (
                    analysis.ai_sentiment_score
                    if analysis.ai_sentiment_score is not None
                    else analysis.sentiment_score
                )

                # Convert risk level
                ai_risk_level = None
                if analysis.risk_level:
                    try:
                        ai_risk_level = RiskLevel(analysis.risk_level.name)
                    except Exception:
                        try:
                            ai_risk_level = RiskLevel(analysis.risk_level.value)
                        except Exception:
                            pass

                ai_dominant_frame = analysis.framing

                ai_sbi_score = None
                if analysis.sbi_result:
                    ai_sbi_score = getattr(analysis.sbi_result, "composite_score", None)

            # Get sentence text if available
            sentence_text = None
            if analysis and analysis.sentence_id:
                sent = await uow.sentences.get(analysis.sentence_id)
                if sent:
                    sentence_text = getattr(sent, "text", None)
            if not sentence_text:
                sent = await uow.sentences.get(command.analysis_id)
                if sent:
                    sentence_text = getattr(sent, "text", None)

            # 2. Determine Agreement Status
            human_risk_level = None
            if command.human_risk:
                try:
                    human_risk_level = RiskLevel(command.human_risk.upper())
                except ValueError:
                    logger.warning(f"Invalid human risk level: {command.human_risk}")

            # Check for disagreements
            has_frame_disagreement = False
            if command.human_frame is not None and ai_dominant_frame is not None:
                has_frame_disagreement = command.human_frame != ai_dominant_frame

            has_risk_disagreement = False
            if human_risk_level is not None and ai_risk_level is not None:
                has_risk_disagreement = human_risk_level != ai_risk_level

            if has_frame_disagreement or has_risk_disagreement:
                agreement_status = AgreementStatus.DISAGREED
            else:
                agreement_status = AgreementStatus.AGREED

            # 3. Construct HumanReview Domain Model
            review = HumanReview(
                analysis_id=command.analysis_id,
                reviewer_id=command.reviewer_id,
                sentence_text=sentence_text,
                ai_sbi_score=ai_sbi_score,
                ai_dominant_frame=ai_dominant_frame,
                ai_risk_level=ai_risk_level,
                ai_sentiment_score=ai_sentiment_score,
                human_sbi_score=command.human_sbi,
                human_dominant_frame=command.human_frame,
                human_risk_level=human_risk_level,
                human_sentiment_score=command.human_sentiment,
                agreement_status=agreement_status,
                disagreement_reason=command.disagreement_reason,
                review_duration_seconds=command.review_duration_seconds,
            )

            # 4. Save to Repository and Commit
            await uow.human_reviews.save(review)
            await uow.commit()

            logger.info(
                "HumanReview submitted successfully",
                extra={
                    "review_id": review.id,
                    "agreement_status": review.agreement_status,
                },
            )
            return review
