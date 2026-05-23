# alembic/versions/2026_05_16_faz4_network_and_dyadic.py
"""Faz 4: Discourse Network Edges + Bilateral Sentiment Extensions.

Revision ID: faz4_network_dyadic_2026
Revises: 050ff3fd782c
Create Date: 2026-05-16 00:50:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "faz4_network_dyadic_2026"
down_revision: str | None = "050ff3fd782c"
depends_on: str | None = None


def upgrade() -> None:
    # Drop the view since discourse_network_edges is changing schema and doesn't support the view columns anymore
    op.execute("DROP VIEW IF EXISTS v_f_fail_network_context")

    # --- discourse_network_edges (Fischer DNA) ---
    op.execute("DROP TABLE IF EXISTS discourse_network_edges")
    op.create_table(
        "discourse_network_edges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("concept_id", sa.String(length=64), nullable=False),
        sa.Column("tf", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("idf", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("weight", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("segment_id", sa.String(length=64), nullable=True),
        sa.Column("panel_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["panel_id"], ["panels.panel_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "actor_id", "concept_id", name="uq_network_edge_actor_concept"
        ),
    )
    op.create_index("ix_net_session", "discourse_network_edges", ["session_id"])
    op.create_index("ix_net_weight", "discourse_network_edges", ["weight"])
    op.create_index("ix_net_actor", "discourse_network_edges", ["actor_id"])

    # --- bilateral_sentiments extensions (Maoz) ---
    with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("vote_affinity", sa.Numeric(12, 6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("alliance_score", sa.Numeric(12, 6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("structural_distance", sa.Numeric(12, 6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("discourse_sentiment_delta", sa.Numeric(12, 6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("maoz_diplomatic_distance", sa.Numeric(12, 6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("maoz_affinity_score", sa.Numeric(12, 6), nullable=True)
        )


def downgrade() -> None:
    op.drop_table("discourse_network_edges")

    # Recreate original discourse_network_edges table
    op.create_table(
        "discourse_network_edges",
        sa.Column("edge_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("panel_id", sa.String(), nullable=True),
        sa.Column("from_country", sa.Text(), nullable=False),
        sa.Column("to_country", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("avg_sentiment", sa.Float(), nullable=False),
        sa.Column("edge_type", sa.Text(), nullable=True),
        sa.Column("power_source", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["panel_id"],
            ["panels.panel_id"],
        ),
        sa.PrimaryKeyConstraint("edge_id"),
    )
    with op.batch_alter_table("discourse_network_edges", schema=None) as batch_op:
        batch_op.create_index("idx_net_from", ["from_country"], unique=False)

    with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
        batch_op.drop_column("vote_affinity")
        batch_op.drop_column("alliance_score")
        batch_op.drop_column("structural_distance")
        batch_op.drop_column("discourse_sentiment_delta")
        batch_op.drop_column("maoz_diplomatic_distance")
        batch_op.drop_column("maoz_affinity_score")

    # Recreate the view as discourse_network_edges is restored to the old schema
    op.execute(
        """
    CREATE VIEW v_f_fail_network_context AS
    SELECT
        f.sent_id, f.speaker_name, f.country, f.check_type,
        dne.from_country, dne.to_country, dne.edge_type,
        cp.relationship_type, cp.affinity_score,
        f.fail_reason AS AI_Neden_Fail
    FROM ai_fail_analysis f
    LEFT JOIN sentences s ON f.sent_id = s.sent_id
    LEFT JOIN discourse_network_edges dne
        ON s.panel_id = dne.panel_id AND s.country = dne.from_country
    LEFT JOIN country_pair_sentiment cp
        ON dne.from_country = cp.from_country AND dne.to_country = cp.to_country
    WHERE f.country NOT IN ('—','Unknown')
    """
    )
