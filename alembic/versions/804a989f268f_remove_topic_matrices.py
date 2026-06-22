"""remove_topic_matrices

Revision ID: 804a989f268f
Revises: 1236a0b96382
Create Date: 2026-06-20 02:49:55.307573

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "804a989f268f"
down_revision: str | None = "1236a0b96382"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Backup topic_matrices to topic_matrices_backup
    op.execute("CREATE TABLE topic_matrices_backup AS SELECT * FROM topic_matrices;")
    # Drop topic_matrices
    op.drop_table("topic_matrices")


def downgrade() -> None:
    # Recreate topic_matrices table
    op.create_table(
        "topic_matrices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("file_id", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("topic_scores", sa.JSON(), nullable=False),
        sa.Column("dominant_topic", sa.String(length=200), nullable=True),
        sa.Column("topic_details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tm_panel_country", "topic_matrices", ["file_id", "country"], unique=True
    )
    # Restore from backup if it exists
    op.execute("INSERT INTO topic_matrices SELECT * FROM topic_matrices_backup;")
    # Drop backup table
    op.execute("DROP TABLE topic_matrices_backup;")
