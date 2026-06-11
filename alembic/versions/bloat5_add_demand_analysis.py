"""bloat5_add_demand_analysis_fields

Revision ID: bloat5_add_demand_analysis
Revises: task_e01_add_comparison_indexes
Create Date: 2026-06-10 00:00:00.000000

Add new fields to demand_records table for enhanced demand analysis.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import JSON, Boolean, DateTime, Float, Text, inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bloat5_add_demand_analysis"
down_revision: str | None = "task_e01_add_comparison_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Helper function to check if column exists
    def column_exists(table_name, column_name):
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns

    # Add new columns to demand_records table
    new_columns = [
        ("timestamp", Float, True),
        ("deadline", Float, True),
        ("compliance_likelihood", Float, True),
        ("assertiveness_score", Float, True),
        ("politeness_score", Float, True),
        ("response_text", Text, True),
        ("response_timestamp", Float, True),
        ("compliance_status", Text, True),
        ("related_demand_ids", JSON, True),
        ("is_conditional", Boolean, False),
        ("conditions", JSON, True),
        ("impact_score", Float, True),
        ("risk_implication", Text, True),
        ("is_active", Boolean, False),
        ("is_fulfilled", Boolean, False),
        ("fulfillment_timestamp", DateTime, True),
        ("notes", Text, True),
        ("tags", JSON, True),
        ("extra_metadata", JSON, True),
    ]

    for column_name, column_type, nullable in new_columns:
        if not column_exists("demand_records", column_name):
            op.add_column(
                "demand_records",
                sa.Column(column_name, column_type, nullable=nullable),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Helper function to check if column exists
    def column_exists(table_name, column_name):
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns

    # Remove new columns from demand_records table
    columns_to_remove = [
        "timestamp",
        "deadline",
        "compliance_likelihood",
        "assertiveness_score",
        "politeness_score",
        "response_text",
        "response_timestamp",
        "compliance_status",
        "related_demand_ids",
        "is_conditional",
        "conditions",
        "impact_score",
        "risk_implication",
        "is_active",
        "is_fulfilled",
        "fulfillment_timestamp",
        "notes",
        "tags",
        "extra_metadata",
    ]

    for column_name in columns_to_remove:
        if column_exists("demand_records", column_name):
            op.drop_column("demand_records", column_name)
