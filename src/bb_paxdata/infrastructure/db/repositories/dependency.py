"""
Repository for Dependency Triples and Actor-Action Matrix.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from bb_paxdata.domain.models.dependency import ActorActionMatrix, DependencyTriple
from bb_paxdata.infrastructure.db.models import (
    ActorActionMatrixORM,
    DependencyTripleORM,
)


class DependencyRepository:
    """
    Handles database operations for dependency triples and actor-action matrices.
    """

    def __init__(self, session: Session):
        self.session = session

    def insert_triple(self, triple: DependencyTriple) -> int:
        """Insert a dependency triple into the database."""
        orm_triple = DependencyTripleORM(
            sent_id=triple.sent_id,
            seg_id=triple.seg_id,
            panel_id=triple.panel_id,
            speaker_name=triple.speaker_name,
            country=triple.country,
            subject_raw=triple.subject_raw,
            subject_resolved=triple.subject_resolved,
            verb_lemma=triple.verb_lemma,
            object_raw=triple.object_raw,
            object_resolved=triple.object_resolved,
            is_passive=1 if triple.is_passive else 0,
            is_negative=1 if triple.is_negative else 0,
            sentiment_context=triple.sentiment_context,
            risk_score=triple.risk_score,
        )
        self.session.add(orm_triple)
        self.session.flush()
        return orm_triple.triple_id

    def upsert_actor_action_matrix(self, matrix: ActorActionMatrix) -> None:
        """Upsert an actor-action matrix entry."""
        # Check if exists
        stmt = select(ActorActionMatrixORM).where(
            ActorActionMatrixORM.panel_id == matrix.panel_id,
            ActorActionMatrixORM.from_country == matrix.from_country,
            ActorActionMatrixORM.to_country == matrix.to_country,
            ActorActionMatrixORM.verb == matrix.verb,
        )
        existing = self.session.execute(stmt).scalar_one_or_none()

        if existing:
            existing.count = matrix.count
            existing.avg_sentiment = matrix.avg_sentiment
            existing.is_passive_pct = matrix.is_passive_pct
            existing.is_negative_pct = matrix.is_negative_pct
        else:
            orm_matrix = ActorActionMatrixORM(
                panel_id=matrix.panel_id,
                from_country=matrix.from_country,
                to_country=matrix.to_country,
                verb=matrix.verb,
                count=matrix.count,
                avg_sentiment=matrix.avg_sentiment,
                is_passive_pct=matrix.is_passive_pct,
                is_negative_pct=matrix.is_negative_pct,
            )
            self.session.add(orm_matrix)

    def get_triples_by_panel(self, panel_id: str) -> list[DependencyTripleORM]:
        """Get all triples for a specific panel."""
        stmt = select(DependencyTripleORM).where(
            DependencyTripleORM.panel_id == panel_id
        )
        return list(self.session.execute(stmt).scalars().all())
