"""add scheduled reports tables

Revision ID: add_scheduled_reports_tables
Revises: add_template_tables
Create Date: 2024-06-24 12:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_scheduled_reports_tables"
down_revision: str | None = "add_template_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduled_reports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=True),
        sa.Column("session_filter", sa.Text(), nullable=True),
        sa.Column("frequency", sa.String(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("time_of_day", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("export_formats", sa.Text(), nullable=True),
        sa.Column("is_active", sa.String(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "distribution_lists",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("scheduled_report_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scheduled_report_id"],
            ["scheduled_reports.id"],
        ),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("consent_given_at", sa.DateTime(), nullable=True),
        sa.Column("consent_token", sa.String(), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(), nullable=True),
        sa.Column("added_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "report_embed_tokens",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("scheduled_report_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scheduled_report_id"],
            ["scheduled_reports.id"],
        ),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("allowed_origins", sa.Text(), nullable=True),
        sa.Column("is_active", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )


def downgrade() -> None:
    op.drop_table("report_embed_tokens")
    op.drop_table("distribution_lists")
    op.drop_table("scheduled_reports")
