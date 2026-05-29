"""add_speaker_profile_columns

Revision ID: 9153500a68a3
Revises: 0762fd4c7846
Create Date: 2026-05-25 17:35:54.701938

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9153500a68a3"
down_revision: Union[str, None] = "0762fd4c7846"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("speaker_profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("first_seen_panel", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "total_duration_sec", sa.Integer(), nullable=False, server_default="0"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("speaker_profiles", schema=None) as batch_op:
        batch_op.drop_column("total_duration_sec")
        batch_op.drop_column("first_seen_panel")
