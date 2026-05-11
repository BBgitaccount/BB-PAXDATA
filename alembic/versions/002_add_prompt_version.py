"""Add prompt_version column to AI analysis tables

Revision ID: 002
Revises: 378a5aaa5bbd
Create Date: 2026-05-11 11:58:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "378a5aaa5bbd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ai_sentence_analysis tablosu
    with op.batch_alter_table("ai_sentence_analysis") as batch_op:
        batch_op.add_column(
            sa.Column(
                "prompt_version",
                sa.String(80),
                nullable=True,
                comment="PromptRegistry versiyonu — '{name}:{ver}:{hash}' formatı",
            )
        )

    # ai_segment_insights tablosu
    with op.batch_alter_table("ai_segment_insights") as batch_op:
        batch_op.add_column(
            sa.Column(
                "prompt_version",
                sa.String(80),
                nullable=True,
                comment="PromptRegistry versiyonu",
            )
        )

    # ai_demand_analysis tablosu
    with op.batch_alter_table("ai_demand_analysis") as batch_op:
        batch_op.add_column(
            sa.Column(
                "prompt_version",
                sa.String(80),
                nullable=True,
                comment="PromptRegistry versiyonu",
            )
        )

    # ai_panel_synthesis tablosu
    with op.batch_alter_table("ai_panel_synthesis") as batch_op:
        batch_op.add_column(
            sa.Column(
                "prompt_version",
                sa.String(80),
                nullable=True,
                comment="PromptRegistry versiyonu",
            )
        )

    # ai_fail_analysis tablosu
    with op.batch_alter_table("ai_fail_analysis") as batch_op:
        batch_op.add_column(
            sa.Column(
                "prompt_version",
                sa.String(80),
                nullable=True,
                comment="PromptRegistry versiyonu",
            )
        )

    # İndeks ekle — prompt versiyonu üzerinden filtreleme için
    with op.batch_alter_table("ai_sentence_analysis") as batch_op:
        batch_op.create_index("idx_ai_sent_prompt_ver", ["prompt_version"])


def downgrade() -> None:
    with op.batch_alter_table("ai_sentence_analysis") as batch_op:
        batch_op.drop_index("idx_ai_sent_prompt_ver")
    for table in [
        "ai_sentence_analysis",
        "ai_segment_insights",
        "ai_demand_analysis",
        "ai_panel_synthesis",
        "ai_fail_analysis",
    ]:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("prompt_version")
