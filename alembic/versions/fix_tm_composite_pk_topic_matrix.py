"""fix_topic_matrix_composite_pk

Fixes the topic_matrix table to use (file_id, country, topic) as a composite
primary key instead of just (country, topic). This matches the ORM model definition
and allows the same country and topic pair to appear in multiple files.

Revision ID: fix_tm_composite_pk
Revises: fix_cs_composite_pk
Create Date: 2026-05-30
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "fix_tm_composite_pk"
down_revision = "fix_cs_composite_pk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER TABLE to change primary keys,
    # so we drop and recreate the table with the correct composite PK.
    op.rename_table("topic_matrix", "topic_matrix_old")

    op.create_table(
        "topic_matrix",
        sa.Column(
            "file_id", sa.String(), sa.ForeignKey("files.file_id"), nullable=False
        ),
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("file_id", "country", "topic"),
    )

    # Copy data from old table (if any exists)
    op.execute(
        "INSERT OR IGNORE INTO topic_matrix "
        "(file_id, country, topic, score) "
        "SELECT file_id, country, topic, score "
        "FROM topic_matrix_old"
    )

    op.drop_table("topic_matrix_old")


def downgrade() -> None:
    # Revert to composite PK without file_id (lossy — duplicates will be dropped)
    op.rename_table("topic_matrix", "topic_matrix_new")

    op.create_table(
        "topic_matrix",
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "file_id", sa.String(), sa.ForeignKey("files.file_id"), nullable=False
        ),
        sa.PrimaryKeyConstraint("country", "topic"),
    )

    op.execute(
        "INSERT OR IGNORE INTO topic_matrix "
        "(country, topic, score, file_id) "
        "SELECT country, topic, score, file_id "
        "FROM topic_matrix_new"
    )

    op.drop_table("topic_matrix_new")
