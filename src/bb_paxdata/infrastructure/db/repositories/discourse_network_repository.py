# src/bb_paxdata/infrastructure/repositories/discourse_network_repository.py
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.domain.models.discourse_network import DiscourseFlow, NetworkEdge
from bb_paxdata.infrastructure.db.discourse_network_table import (
    DiscourseNetworkEdgeTable,
)
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository


class DiscourseNetworkRepository(BaseRepository[DiscourseNetworkEdgeTable]):
    """Persistence for Fischer DNA bipartite edges."""

    model_class = DiscourseNetworkEdgeTable

    async def save_flow(self, session: AsyncSession, flow: DiscourseFlow) -> None:
        """Persist all edges from a DiscourseFlow (upsert semantics)."""
        # Clear existing edges for this session to maintain idempotency
        await session.execute(
            delete(DiscourseNetworkEdgeTable).where(
                DiscourseNetworkEdgeTable.session_id == flow.session_id
            )
        )

        for edge in flow.edges:
            db_edge = DiscourseNetworkEdgeTable(
                session_id=flow.session_id,
                actor_id=edge.actor_id,
                concept_id=edge.concept_id,
                tf=edge.tf_score,
                idf=edge.idf_score,
                weight=edge.weight,
                segment_id=edge.segment_source_id,
            )
            session.add(db_edge)

        await session.flush()

    async def get_flow_by_session(
        self, session: AsyncSession, session_id: str
    ) -> DiscourseFlow:
        """Reconstruct DiscourseFlow from persisted edges."""
        result = await session.execute(
            select(DiscourseNetworkEdgeTable).where(
                DiscourseNetworkEdgeTable.session_id == session_id
            )
        )
        rows = result.scalars().all()

        flow = DiscourseFlow(session_id=session_id)
        for row in rows:
            edge = NetworkEdge(
                actor_id=row.actor_id,
                concept_id=row.concept_id,
                tf_score=row.tf,
                idf_score=row.idf,
                weight=row.weight,
                segment_source_id=row.segment_id,
            )
            flow = flow.add_edge(edge)
        return flow

    async def get_top_edges_for_actor(
        self,
        session: AsyncSession,
        session_id: str,
        actor_id: str,
        limit: int = 20,
    ) -> Sequence[NetworkEdge]:
        """Retrieve highest-weight edges for a specific actor."""
        result = await session.execute(
            select(DiscourseNetworkEdgeTable)
            .where(
                DiscourseNetworkEdgeTable.session_id == session_id,
                DiscourseNetworkEdgeTable.actor_id == actor_id,
            )
            .order_by(DiscourseNetworkEdgeTable.weight.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return tuple(
            NetworkEdge(
                actor_id=r.actor_id,
                concept_id=r.concept_id,
                tf_score=r.tf,
                idf_score=r.idf,
                weight=r.weight,
                segment_source_id=r.segment_id,
            )
            for r in rows
        )
