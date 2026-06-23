"""actor_table_audit

Revision ID: bb4a989f268f
Revises: 804a989f268f
Create Date: 2026-06-23 19:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bb4a989f268f"
down_revision: str | None = "804a989f268f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Drop existing actor_action_matrix
    op.drop_table("actor_action_matrix")

    # 2. Recreate actor_action_matrix with correct columns
    op.create_table(
        "actor_action_matrix",
        sa.Column("matrix_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.String(length=255), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column(
            "last_updated",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("matrix_id"),
    )
    with op.batch_alter_table("actor_action_matrix", schema=None) as batch_op:
        batch_op.create_index("idx_matrix_panel", ["file_id"], unique=False)
        batch_op.create_index("idx_matrix_actor", ["actor_id"], unique=False)
        batch_op.create_index("idx_matrix_action", ["action_type"], unique=False)

    # 3. Add risk columns to actor_topic_projection
    with op.batch_alter_table("actor_topic_projection", schema=None) as batch_op:
        batch_op.add_column(sa.Column("risk_score_raw", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("risk_score_weighted", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("risk_score_normalized", sa.Float(), nullable=True)
        )

    # 4. Add power_level to segment_events
    with op.batch_alter_table("segment_events", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("power_level", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    # 1. Drop power_level from segment_events
    with op.batch_alter_table("segment_events", schema=None) as batch_op:
        batch_op.drop_column("power_level")

    # 2. Drop risk columns from actor_topic_projection
    with op.batch_alter_table("actor_topic_projection", schema=None) as batch_op:
        batch_op.drop_column("risk_score_raw")
        batch_op.drop_column("risk_score_weighted")
        batch_op.drop_column("risk_score_normalized")

    # 3. Drop actor_action_matrix
    op.drop_table("actor_action_matrix")

    # 4. Recreate old actor_action_matrix
    op.create_table(
        "actor_action_matrix",
        sa.Column("matrix_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.String(length=255), nullable=False),
        sa.Column("from_country", sa.Text(), nullable=False),
        sa.Column("to_country", sa.Text(), nullable=False),
        sa.Column("verb", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("avg_sentiment", sa.Float(), nullable=False),
        sa.Column("is_passive_pct", sa.Float(), nullable=False),
        sa.Column("is_negative_pct", sa.Float(), nullable=False),
        sa.Column(
            "last_updated",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("matrix_id"),
    )
    with op.batch_alter_table("actor_action_matrix", schema=None) as batch_op:
        batch_op.create_index("idx_matrix_from", ["from_country"], unique=False)
        batch_op.create_index("idx_matrix_panel", ["file_id"], unique=False)
        batch_op.create_index("idx_matrix_to", ["to_country"], unique=False)
