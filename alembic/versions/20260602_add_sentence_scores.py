"""add_sentence_scores

Revision ID: 20260602_ss
Revises: f904f26a70c1
Create Date: 2026-06-02 12:00:00.000000

"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260602_ss"
down_revision: str | Sequence[str] | None = "f904f26a70c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "sentences" not in tables:
        return

    cols = [c["name"] for c in inspector.get_columns("sentences")]

    if "formula_inconsistency_score" not in cols:
        with op.batch_alter_table("sentences", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "formula_inconsistency_score",
                    sa.Float(),
                    nullable=False,
                    server_default=sa.text("0.0"),
                )
            )
    if "discrepancy_score" not in cols:
        with op.batch_alter_table("sentences", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "discrepancy_score",
                    sa.Float(),
                    nullable=False,
                    server_default=sa.text("0.0"),
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "sentences" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("sentences")]
    if "discrepancy_score" in cols:
        with op.batch_alter_table("sentences", schema=None) as batch_op:
            batch_op.drop_column("discrepancy_score")
    if "formula_inconsistency_score" in cols:
        with op.batch_alter_table("sentences", schema=None) as batch_op:
            batch_op.drop_column("formula_inconsistency_score")
