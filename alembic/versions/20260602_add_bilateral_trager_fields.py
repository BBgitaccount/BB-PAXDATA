"""add_bilateral_trager_fields

Revision ID: 20260602_bt
Revises: 20260602_ss
Create Date: 2026-06-02 12:05:00.000000

"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260602_bt"
down_revision: str | Sequence[str] | None = "20260602_ss"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "bilateral_sentiments" not in tables:
        return

    cols = [c["name"] for c in inspector.get_columns("bilateral_sentiments")]

    if "power_level_a" not in cols:
        with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "power_level_a",
                    sa.Float(),
                    nullable=False,
                    server_default=sa.text("1.0"),
                )
            )
    if "power_level_b" not in cols:
        with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "power_level_b",
                    sa.Float(),
                    nullable=False,
                    server_default=sa.text("1.0"),
                )
            )
    if "demand_weight" not in cols:
        with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "demand_weight",
                    sa.Float(),
                    nullable=False,
                    server_default=sa.text("1.0"),
                )
            )
    if "risk_severity" not in cols:
        with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "risk_severity",
                    sa.Float(),
                    nullable=False,
                    server_default=sa.text("1.0"),
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "bilateral_sentiments" not in inspector.get_table_names():
        return
    cols = [c["name"] for c in inspector.get_columns("bilateral_sentiments")]
    if "risk_severity" in cols:
        with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
            batch_op.drop_column("risk_severity")
    if "demand_weight" in cols:
        with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
            batch_op.drop_column("demand_weight")
    if "power_level_b" in cols:
        with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
            batch_op.drop_column("power_level_b")
    if "power_level_a" in cols:
        with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
            batch_op.drop_column("power_level_a")
