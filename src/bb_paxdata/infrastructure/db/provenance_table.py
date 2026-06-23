from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base


class ProvenanceGraphORM(Base):
    """SQLAlchemy ORM model for storing provenance graphs."""

    __tablename__ = "provenance_graphs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    result_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    nodes: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    edges: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")

    def to_domain_model(self):
        """Convert ORM to domain model."""
        from bb_paxdata.application.domain.models.provenance import (
            ProvenanceEdge,
            ProvenanceGraph,
            ProvenanceNode,
        )

        nodes = [ProvenanceNode(**node) for node in self.nodes]
        edges = [ProvenanceEdge(**edge) for edge in self.edges]

        return ProvenanceGraph(
            id=uuid.UUID(self.id),
            result_id=self.result_id,
            nodes=nodes,
            edges=edges,
            created_at=self.created_at,
            correlation_id=self.correlation_id,
        )
