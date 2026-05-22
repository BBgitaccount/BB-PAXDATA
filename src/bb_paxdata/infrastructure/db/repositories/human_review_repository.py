"""HumanReviewRepository — domain ↔ ORM mapping and async CRUD.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.domain.models.human_review import (
    AgreementStatus,
    HumanReview,
    RiskLevel,
)
from bb_paxdata.infrastructure.db.human_review_table import HumanReviewORM

logger = logging.getLogger(__name__)


class HumanReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, review: HumanReview) -> None:
        orm = self._to_orm(review)
        self._session.add(orm)
        logger.info("Saved HumanReview", extra={"id": review.id})

    async def get_by_analysis_id(self, analysis_id: str) -> list[HumanReview]:
        stmt = select(HumanReviewORM).where(HumanReviewORM.analysis_id == analysis_id)
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_disagreements_for_prompt(
        self,
        prompt_version: str,
        limit: int = 50,
    ) -> list[HumanReview]:
        from bb_paxdata.infrastructure.db.models import AISentenceAnalysis, Sentence

        stmt = (
            select(HumanReviewORM, Sentence.text)
            .outerjoin(
                AISentenceAnalysis,
                HumanReviewORM.analysis_id == AISentenceAnalysis.sent_id,
            )
            .outerjoin(Sentence, AISentenceAnalysis.sent_id == Sentence.sent_id)
            .where(
                and_(
                    AISentenceAnalysis.prompt_version == prompt_version,
                    HumanReviewORM.agreement_status.in_(
                        [AgreementStatus.DISAGREED.value, AgreementStatus.PARTIAL.value]
                    ),
                    HumanReviewORM.disagreement_reason.isnot(None),
                )
            )
            .order_by(HumanReviewORM.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row[0], row[1]) for row in result.all()]

    async def get_reviews_for_prompt(
        self,
        prompt_version: str,
        limit: int = 100,
    ) -> list[HumanReview]:
        from bb_paxdata.infrastructure.db.models import AISentenceAnalysis, Sentence

        stmt = (
            select(HumanReviewORM, Sentence.text)
            .outerjoin(
                AISentenceAnalysis,
                HumanReviewORM.analysis_id == AISentenceAnalysis.sent_id,
            )
            .outerjoin(Sentence, AISentenceAnalysis.sent_id == Sentence.sent_id)
            .where(AISentenceAnalysis.prompt_version == prompt_version)
            .order_by(HumanReviewORM.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row[0], row[1]) for row in result.all()]

    async def get_gold_standard_examples(
        self,
        frame_type: str | None = None,
        limit: int = 5,
    ) -> list[HumanReview]:
        from bb_paxdata.infrastructure.db.models import AISentenceAnalysis, Sentence

        conditions: list[Any] = [
            HumanReviewORM.human_dominant_frame.isnot(None),
        ]
        if frame_type:
            conditions.append(HumanReviewORM.human_dominant_frame == frame_type)
        stmt = (
            select(HumanReviewORM, Sentence.text)
            .outerjoin(
                AISentenceAnalysis,
                HumanReviewORM.analysis_id == AISentenceAnalysis.sent_id,
            )
            .outerjoin(Sentence, AISentenceAnalysis.sent_id == Sentence.sent_id)
            .where(and_(*conditions))
            .order_by(HumanReviewORM.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row[0], row[1]) for row in result.all()]

    @staticmethod
    def _to_orm(review: HumanReview) -> HumanReviewORM:
        return HumanReviewORM(
            id=review.id,
            analysis_id=review.analysis_id,
            reviewer_id=review.reviewer_id,
            ai_sbi_score=review.ai_sbi_score,
            ai_dominant_frame=review.ai_dominant_frame,
            ai_risk_level=review.ai_risk_level.value if review.ai_risk_level else None,
            ai_sentiment_score=review.ai_sentiment_score,
            human_sbi_score=review.human_sbi_score,
            human_dominant_frame=review.human_dominant_frame,
            human_risk_level=(
                review.human_risk_level.value if review.human_risk_level else None
            ),
            human_sentiment_score=review.human_sentiment_score,
            agreement_status=review.agreement_status.value,
            disagreement_reason=review.disagreement_reason,
            review_duration_seconds=review.review_duration_seconds,
            has_frame_disagreement=review.has_frame_disagreement,
            has_risk_disagreement=review.has_risk_disagreement,
            sbi_delta=review.sbi_delta,
            created_at=review.created_at,
        )

    @staticmethod
    def _to_domain(
        orm: HumanReviewORM, sentence_text: str | None = None
    ) -> HumanReview:
        return HumanReview(
            id=orm.id,
            analysis_id=orm.analysis_id,
            reviewer_id=orm.reviewer_id,
            sentence_text=sentence_text,
            ai_sbi_score=orm.ai_sbi_score,
            ai_dominant_frame=orm.ai_dominant_frame,
            ai_risk_level=RiskLevel(orm.ai_risk_level) if orm.ai_risk_level else None,
            ai_sentiment_score=orm.ai_sentiment_score,
            human_sbi_score=orm.human_sbi_score,
            human_dominant_frame=orm.human_dominant_frame,
            human_risk_level=(
                RiskLevel(orm.human_risk_level) if orm.human_risk_level else None
            ),
            human_sentiment_score=orm.human_sentiment_score,
            agreement_status=AgreementStatus(orm.agreement_status),
            disagreement_reason=orm.disagreement_reason,
            review_duration_seconds=orm.review_duration_seconds,
            has_frame_disagreement=orm.has_frame_disagreement,
            has_risk_disagreement=orm.has_risk_disagreement,
            sbi_delta=orm.sbi_delta,
            created_at=orm.created_at,
        )
