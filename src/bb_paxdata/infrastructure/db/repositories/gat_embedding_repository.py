"""GATEmbeddingRepository — Infrastructure implementation of IGATEmbeddingRepository.

(GAP-01, M-05) Implements the domain port interface using SQLAlchemy ORM.
Converts between GATEmbeddingTable ORM and GATEmbedding domain model.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.gat_models import GATEmbedding
from bb_paxdata.application.domain.ports.i_gat_embedding_repository import (
    IGATEmbeddingRepository,
)
from bb_paxdata.infrastructure.db.models.gat_embedding_table import (
    GATEmbeddingTable,
)


class GATEmbeddingRepository(IGATEmbeddingRepository):
    """SQLAlchemy implementation of the GAT embedding repository port.

    Conversion notes:
        - embedding_json (JSON string in table) ↔ embedding (list[float] in domain)
        - characteristic_concepts_json (JSON string) ↔ characteristic_concepts (list[str])
        - anomaly_score is stored directly as float
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_actor_and_session(
        self, actor_id: str, session_id: str
    ) -> GATEmbedding | None:
        stmt = select(GATEmbeddingTable).where(
            GATEmbeddingTable.actor_id == actor_id,
            GATEmbeddingTable.session_id == session_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    async def save(self, embedding: GATEmbedding) -> None:
        orm = self._to_orm(embedding)
        self._session.add(orm)

    async def save_batch(self, embeddings: Sequence[GATEmbedding]) -> None:
        orm_objects = [self._to_orm(emb) for emb in embeddings]
        self._session.add_all(orm_objects)

    # ── Dönüşüm Yardımcıları ──────────────────────────────────────────────

    @staticmethod
    def _to_orm(domain: GATEmbedding) -> GATEmbeddingTable:
        return GATEmbeddingTable(
            actor_id=domain.actor_id,
            session_id=domain.session_id,
            embedding_json=json.dumps(domain.embedding),
            characteristic_concepts_json=(
                json.dumps(domain.characteristic_concepts)
                if domain.characteristic_concepts
                else None
            ),
            anomaly_score=domain.anomaly_score,
            computed_at=domain.computed_at,
        )

    @staticmethod
    def _to_domain(row: GATEmbeddingTable) -> GATEmbedding:
        embedding = json.loads(row.embedding_json)
        characteristic_concepts: list[str] = []
        if row.characteristic_concepts_json:
            characteristic_concepts = json.loads(row.characteristic_concepts_json)
        return GATEmbedding(
            actor_id=row.actor_id,
            session_id=row.session_id,
            embedding=embedding,
            characteristic_concepts=characteristic_concepts,
            anomaly_score=row.anomaly_score,
            computed_at=row.computed_at,
        )
