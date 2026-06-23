from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.provenance import ProvenanceGraph
from bb_paxdata.infrastructure.db.provenance_table import ProvenanceGraphORM


class ProvenanceRepository:
    """Repository for provenance graph persistence and retrieval."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, graph: ProvenanceGraph) -> ProvenanceGraph:
        """Save a provenance graph to the database."""
        nodes_data = [node.model_dump() for node in graph.nodes]
        edges_data = [edge.model_dump() for edge in graph.edges]

        orm = ProvenanceGraphORM(
            id=str(graph.id),
            result_id=graph.result_id,
            correlation_id=graph.correlation_id,
            nodes=nodes_data,
            edges=edges_data,
            created_at=graph.created_at,
            version=graph.nodes[0].version if graph.nodes else "1.0",
        )

        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)

        return orm.to_domain_model()

    async def get_by_result_id(self, result_id: str) -> ProvenanceGraph | None:
        """Retrieve a provenance graph by its result ID."""
        stmt = select(ProvenanceGraphORM).where(
            ProvenanceGraphORM.result_id == result_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()

        if orm:
            return orm.to_domain_model()
        return None

    async def get_by_id(self, graph_id: str) -> ProvenanceGraph | None:
        """Retrieve a provenance graph by its ID."""
        stmt = select(ProvenanceGraphORM).where(ProvenanceGraphORM.id == graph_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()

        if orm:
            return orm.to_domain_model()
        return None

    async def get_by_correlation_id(self, correlation_id: str) -> list[ProvenanceGraph]:
        """Retrieve all provenance graphs for a given correlation ID."""
        stmt = select(ProvenanceGraphORM).where(
            ProvenanceGraphORM.correlation_id == correlation_id
        )
        result = await self._session.execute(stmt)
        orms = result.scalars().all()

        return [orm.to_domain_model() for orm in orms]
