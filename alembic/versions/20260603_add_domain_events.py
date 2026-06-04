"""add_domain_events_worm_table

Revision ID: 20260603_ade
Revises: 20260602_merge
Create Date: 2026-06-03 20:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260603_ade"
down_revision: str | Sequence[str] | None = "20260602_merge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "domain_events" not in tables:
        op.create_table(
            "domain_events",
            sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("aggregate_type", sa.String(length=64), nullable=False),
            sa.Column("aggregate_id", sa.String(length=128), nullable=False),
            sa.Column("event_type", sa.String(length=128), nullable=False),
            sa.Column(
                "event_version", sa.Integer(), server_default="1", nullable=False
            ),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("actor_id", sa.String(length=128), nullable=True),
            sa.Column("correlation_id", sa.String(length=64), nullable=True),
            sa.Column(
                "occurred_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_domain_events_aggregate",
            "domain_events",
            ["aggregate_type", "aggregate_id"],
        )
        op.create_index(
            "ix_domain_events_type_time",
            "domain_events",
            ["event_type", "occurred_at"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "domain_events" in tables:
        op.drop_index("ix_domain_events_type_time", table_name="domain_events")
        op.drop_index("ix_domain_events_aggregate", table_name="domain_events")
        op.drop_table("domain_events")
