"""add_detailed_pattern_records_fields

Revision ID: 13b6b75a4194
Revises: 313083ab4704
Create Date: 2026-05-26 15:18:49.290469

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "13b6b75a4194"
down_revision: str | None = "313083ab4704"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop broken legacy view that blocks SQLite table renames
    op.execute("DROP VIEW IF EXISTS v_diplomatic_network")

    # 1. Add columns as nullable
    with op.batch_alter_table("pattern_records", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pattern_subtype", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("matched_keyword", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("prev_sentence", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("next_sentence", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("risk_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sentiment_category", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))

    # 2. Backfill existing nulls
    op.execute("UPDATE pattern_records SET risk_score = 0 WHERE risk_score IS NULL")
    op.execute(
        "UPDATE pattern_records SET sentiment_category = 'unknown' WHERE sentiment_category IS NULL"
    )
    op.execute(
        "UPDATE pattern_records SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
    )

    # 3. Add constraints and defaults
    with op.batch_alter_table("pattern_records", schema=None) as batch_op:
        batch_op.alter_column("risk_score", nullable=False, server_default="0")
        batch_op.alter_column(
            "created_at", server_default=sa.text("(CURRENT_TIMESTAMP)")
        )
        batch_op.create_check_constraint(
            "check_risk_score_range", "risk_score >= 0 AND risk_score <= 10"
        )
        batch_op.create_check_constraint(
            "check_sentiment_category",
            "sentiment_category IN ('cooperative', 'confrontational', 'concerned', 'neutral_cautious', 'constructive', 'neutral', 'unknown')",
        )
        batch_op.create_unique_constraint(
            "uq_pattern_per_sentence", ["sent_id", "pattern_type", "matched_keyword"]
        )


def downgrade() -> None:
    with op.batch_alter_table("pattern_records", schema=None) as batch_op:
        batch_op.drop_constraint("uq_pattern_per_sentence", type_="unique")
        batch_op.drop_constraint("check_sentiment_category", type_="check")
        batch_op.drop_constraint("check_risk_score_range", type_="check")
        batch_op.drop_column("created_at")
        batch_op.drop_column("sentiment_category")
        batch_op.drop_column("risk_score")
        batch_op.drop_column("next_sentence")
        batch_op.drop_column("prev_sentence")
        batch_op.drop_column("matched_keyword")
        batch_op.drop_column("pattern_subtype")
