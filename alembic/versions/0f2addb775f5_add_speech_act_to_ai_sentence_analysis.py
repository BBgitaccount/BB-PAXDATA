"""add_speech_act_to_ai_sentence_analysis

Revision ID: 0f2addb775f5
Revises: arg_graph_v1
Create Date: 2026-06-05 02:23:11.304824

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0f2addb775f5"
down_revision: str | None = "arg_graph_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_sentence_analysis", schema=None) as batch_op:
        batch_op.add_column(sa.Column("speech_act_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_sentence_analysis", schema=None) as batch_op:
        batch_op.drop_column("speech_act_json")
