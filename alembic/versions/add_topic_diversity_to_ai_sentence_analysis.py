"""add_topic_diversity_to_ai_sentence_analysis

Revision ID: add_topic_diversity
Revises: task_e01_add_comparison_indexes
Create Date: 2026-06-08 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_topic_diversity"
down_revision: str | None = "task_e01_add_comparison_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_sentence_analysis", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "topic_diversity",
                sa.Float(),
                nullable=True,
                comment="Shannon entropy of BERTopic P(topic|doc) distribution (Faz 5). 0.0 = fully focused, higher = dispersed topic signal.",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_sentence_analysis", schema=None) as batch_op:
        batch_op.drop_column("topic_diversity")
