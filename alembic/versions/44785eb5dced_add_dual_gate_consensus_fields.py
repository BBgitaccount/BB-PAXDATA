"""add_dual_gate_consensus_fields

Revision ID: 44785eb5dced
Revises: 1ef902da8b4f
Create Date: 2026-05-18 13:13:58.853432

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "44785eb5dced"
down_revision: Union[str, None] = "1ef902da8b4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_sentence_analysis", sa.Column("coherence_score", sa.Float(), nullable=True)
    )
    op.add_column(
        "ai_sentence_analysis",
        sa.Column("anomaly_consensus_level", sa.String(30), nullable=True),
    )
    op.add_column(
        "ai_sentence_analysis",
        sa.Column("anomaly_ai_decision", sa.String(20), nullable=True),
    )
    op.add_column(
        "ai_sentence_analysis",
        sa.Column("anomaly_ai_reasoning", sa.String(1000), nullable=True),
    )
    op.add_column(
        "ai_sentence_analysis",
        sa.Column("anomaly_detected_subtype", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_sentence_analysis", "anomaly_detected_subtype")
    op.drop_column("ai_sentence_analysis", "anomaly_ai_reasoning")
    op.drop_column("ai_sentence_analysis", "anomaly_ai_decision")
    op.drop_column("ai_sentence_analysis", "anomaly_consensus_level")
    op.drop_column("ai_sentence_analysis", "coherence_score")
