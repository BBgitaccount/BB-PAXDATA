"""add_nlp_columns_to_words

Revision ID: 3e039beef918
Revises: 8a350fdca574
Create Date: 2026-06-19 01:13:33.842538

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e039beef918"
down_revision: str | None = "8a350fdca574"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("words", sa.Column("lemma", sa.Text(), nullable=True))
    op.add_column("words", sa.Column("pos_tag", sa.Text(), nullable=True))
    op.add_column("words", sa.Column("dep_label", sa.Text(), nullable=True))
    op.add_column("words", sa.Column("entity_type", sa.Text(), nullable=True))
    op.add_column(
        "words",
        sa.Column(
            "is_negated", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "words",
        sa.Column(
            "is_hedge", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "words",
        sa.Column(
            "is_diplomatic_term",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("words", sa.Column("char_offset_start", sa.Integer(), nullable=True))
    op.add_column("words", sa.Column("char_offset_end", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("words", "char_offset_end")
    op.drop_column("words", "char_offset_start")
    op.drop_column("words", "is_diplomatic_term")
    op.drop_column("words", "is_hedge")
    op.drop_column("words", "is_negated")
    op.drop_column("words", "entity_type")
    op.drop_column("words", "dep_label")
    op.drop_column("words", "pos_tag")
    op.drop_column("words", "lemma")
