"""
Repository for Explainability data.
"""

import json
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from bb_paxdata.domain.models.explanation import SentenceExplanation
from bb_paxdata.infrastructure.db.models import AIExplanationsORM


class ExplanationRepository:
    """
    Handles database operations for AI explanations.
    """

    def __init__(self, session: Session):
        self.session = session

    def insert_explanation(self, explanation: SentenceExplanation) -> int:
        """Insert a sentence explanation into the database."""
        token_attr_json = None
        if explanation.token_attributions:
            token_attr_json = json.dumps(
                [attr.model_dump() for attr in explanation.token_attributions]
            )

        orm_exp = AIExplanationsORM(
            sent_id=explanation.sent_id,
            risk_explanation=explanation.risk_explanation,
            sentiment_explanation=explanation.sentiment_explanation,
            grammatical_explanation=explanation.grammatical_explanation,
            discrepancy_explanation=explanation.discrepancy_explanation,
            executive_summary=explanation.executive_summary,
            token_attributions_json=token_attr_json,
        )
        self.session.add(orm_exp)
        self.session.flush()
        return cast(int, orm_exp.explanation_id)

    def get_by_sentence(self, sent_id: str) -> AIExplanationsORM | None:
        """Get explanation for a specific sentence."""
        stmt = select(AIExplanationsORM).where(AIExplanationsORM.sent_id == sent_id)
        return self.session.execute(stmt).scalar_one_or_none()
