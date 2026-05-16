# src/bb_paxdata/infrastructure/db/discourse_network_table.py
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bb_paxdata.infrastructure.db.base import Base

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.db.models import Panel


class DiscourseNetworkEdgeTable(Base):
    """Fischer DNA: Sparse bipartite edge storage (Actor ↔ Concept)."""

    __tablename__ = "discourse_network_edges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)

    # Bipartite nodes
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    concept_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Fischer weights
    tf: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    idf: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, index=True)

    # Provenance
    segment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    panel_id: Mapped[str | None] = mapped_column(
        ForeignKey("panels.panel_id", ondelete="CASCADE"), nullable=True
    )

    # Relationships
    panel: Mapped[Panel] = relationship(back_populates="network_edges")

    __table_args__ = (
        UniqueConstraint(
            "session_id", "actor_id", "concept_id", name="uq_network_edge_actor_concept"
        ),
        Index("ix_net_weight_high", "weight", postgresql_where="weight > 0.5"),
    )
