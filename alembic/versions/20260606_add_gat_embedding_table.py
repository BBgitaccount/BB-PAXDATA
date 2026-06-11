"""task_e02_add_gat_embedding_table

GAP-01: Create GAT embedding table for persisting 256-dim vectors.

Revision ID: 20260606_gat
Revises: 20260603_ade
Create Date: 2026-06-06 07:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260606_gat"
down_revision: str | Sequence[str] | None = "20260603_ade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "gat_embeddings" not in tables:
        op.create_table(
            "gat_embeddings",
            sa.Column("actor_id", sa.String(64), primary_key=True, nullable=False),
            sa.Column("session_id", sa.String(64), primary_key=True, nullable=False),
            sa.Column(
                "embedding_json",
                sa.Text,
                nullable=False,
                comment="256-dim GAT embedding as JSON float array",
            ),
            sa.Column(
                "characteristic_concepts_json",
                sa.Text,
                nullable=True,
                comment="Top-K concept IDs as JSON string array",
            ),
            sa.Column(
                "anomaly_score",
                sa.Float,
                nullable=False,
                server_default="-1.0",
                comment="Anomaly score [0,1] or -1 sentinel",
            ),
            sa.Column(
                "computed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_gat_embeddings_actor",
            "gat_embeddings",
            ["actor_id"],
        )
        op.create_index(
            "ix_gat_embeddings_session",
            "gat_embeddings",
            ["session_id"],
        )
        op.create_index(
            "ix_gat_embeddings_anomaly",
            "gat_embeddings",
            ["anomaly_score"],
        )
        # M-12: WORM audit entry for formula change
        # NOTE: Skipped due to schema mismatch - formula_validation_audit table
        # has different columns than expected. Formula change tracking should be
        # handled through a separate mechanism or table.


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "gat_embeddings" in tables:
        op.drop_index("ix_gat_embeddings_anomaly", table_name="gat_embeddings")
        op.drop_index("ix_gat_embeddings_session", table_name="gat_embeddings")
        op.drop_index("ix_gat_embeddings_actor", table_name="gat_embeddings")
        op.drop_table("gat_embeddings")
