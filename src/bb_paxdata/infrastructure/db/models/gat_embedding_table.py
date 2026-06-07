"""GATEmbedding ORM model for SQLAlchemy 2.0 async.

(GAP-01) GATEmbeddingTable provides persistence for GATEmbedding domain objects.
Composite primary key: (actor_id, session_id).

WORM semantics: records are immutable once written (no UPDATE/DELETE).
"""

from __future__ import annotations

from datetime import datetime, timezone

from bb_paxdata.infrastructure.db.base import Base
from sqlalchemy import (
    DateTime,
    Float,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class GATEmbeddingTable(Base):
    """Persistent storage for GAT embedding vectors and anomaly scores.

    (GAP-01) Designed for Write-Once-Read-Many (WORM) usage:
    - INSERT only; never UPDATE or DELETE
    - Composite PK (actor_id, session_id)
    - embedding stored as JSON string (DB-agnostic; use pgvector ARRAY for Postgres)
    """

    __tablename__ = "gat_embeddings"

    actor_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # 256-dim embedding stored as JSON array for SQLite compatibility
    # On PostgreSQL, migrate to pgvector ARRAY for similarity search
    embedding_json: Mapped[str] = mapped_column(
        Text, nullable=False, comment="256-dim GAT embedding as JSON float array"
    )

    # Top characteristic concepts as JSON array
    characteristic_concepts_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Top-K concept IDs as JSON string array"
    )

    # Anomaly score: [0.0, 1.0] or -1.0 sentinel
    anomaly_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=-1.0, comment="Anomaly score or -1 sentinel"
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_gat_embeddings_actor", "actor_id"),
        Index("ix_gat_embeddings_session", "session_id"),
        Index("ix_gat_embeddings_anomaly", "anomaly_score"),
    )
