"""
Repository for Dependency Triples and Actor-Action Matrix.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.dependency import (
    ActorActionMatrix,
    DependencyTriple,
)
from bb_paxdata.infrastructure.db.models import (
    ActorActionMatrixORM,
    DependencyTripleORM,
)


class DependencyRepository:
    """
    Handles database operations for dependency triples and actor-action matrices.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_triple(self, triple: DependencyTriple) -> int:
        """Insert a dependency triple into the database."""
        orm_triple = DependencyTripleORM(
            sent_id=triple.sent_id,
            seg_id=triple.seg_id,
            file_id=triple.panel_id,
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
        await self.session.flush()
        return orm_triple.triple_id

    async def upsert_actor_action_matrix(self, matrix: ActorActionMatrix) -> None:
        """Upsert an actor-action matrix entry."""
        # Check if exists
        stmt = select(ActorActionMatrixORM).where(
            ActorActionMatrixORM.file_id == matrix.panel_id,
            ActorActionMatrixORM.actor_id == matrix.actor_id,
            ActorActionMatrixORM.action_type == matrix.action_type,
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.count = matrix.count
            existing.weight = matrix.weight
        else:
            orm_matrix = ActorActionMatrixORM(
                file_id=matrix.panel_id,
                actor_id=matrix.actor_id,
                action_type=matrix.action_type,
                count=matrix.count,
                weight=matrix.weight,
            )
            self.session.add(orm_matrix)
        await self.session.flush()

    async def get_triples_by_panel(self, file_id: str) -> list[DependencyTripleORM]:
        """Get all triples for a specific panel."""
        stmt = select(DependencyTripleORM).where(DependencyTripleORM.file_id == file_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def delete_by_panel(self, file_id: str) -> None:
        """Delete all DependencyTripleORM and ActorActionMatrixORM entries associated with a panel."""
        from sqlalchemy import delete

        await self.session.execute(
            delete(DependencyTripleORM).where(DependencyTripleORM.file_id == file_id)
        )
        await self.session.execute(
            delete(ActorActionMatrixORM).where(ActorActionMatrixORM.file_id == file_id)
        )
        await self.session.flush()
