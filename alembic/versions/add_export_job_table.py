"""add export job table

Revision ID: add_export_job
Revises:
Create Date: 2024-06-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_export_job"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("file_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.file_id"],
        ),
        sa.Column("export_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("progress_pct", sa.Integer(), nullable=True),
        sa.Column("options", sa.Text(), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_export_jobs_file_id"), "export_jobs", ["file_id"], unique=False
    )
    op.create_index(
        op.f("ix_export_jobs_status"), "export_jobs", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_export_jobs_status"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_file_id"), table_name="export_jobs")
    op.drop_table("export_jobs")
