"""add_narrative_to_discourse_flows

Revision ID: c9e693fb9bfb
Revises: 0f2addb775f5
Create Date: 2026-06-05 03:44:20.693370

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e693fb9bfb"
down_revision: Union[str, None] = "0f2addb775f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("discourse_flows")}

    if "narrative_layer" not in existing_cols:
        op.add_column(
            "discourse_flows",
            sa.Column("narrative_layer", sa.String(length=50), nullable=True),
        )
    if "narrative_target_actor" not in existing_cols:
        op.add_column(
            "discourse_flows",
            sa.Column("narrative_target_actor", sa.String(length=100), nullable=True),
        )
    if "narrative_salience" not in existing_cols:
        op.add_column(
            "discourse_flows",
            sa.Column(
                "narrative_salience",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0.0"),
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("discourse_flows") as batch_op:
        batch_op.drop_column("narrative_salience")
        batch_op.drop_column("narrative_target_actor")
        batch_op.drop_column("narrative_layer")
