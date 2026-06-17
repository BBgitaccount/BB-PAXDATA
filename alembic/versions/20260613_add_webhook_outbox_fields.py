"""add_webhook_outbox_fields

Revision ID: 20260613_awof
Revises: e2d168f7adc3
Create Date: 2026-06-13 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260613_awof"
down_revision: str | Sequence[str] | None = "e2d168f7adc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 0. Create outbox_events table if it does not exist yet.
    #    (No earlier migration creates this table; this migration is its origin.)
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "outbox_events" not in existing_tables:
        op.create_table(
            "outbox_events",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("aggregate_id", sa.String(length=36), nullable=False),
            sa.Column("aggregate_type", sa.String(length=100), nullable=False),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column(
                "status", sa.String(length=20), server_default="pending", nullable=False
            ),
            sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
        op.create_index(
            "ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"]
        )

    # 1. Create webhook_subscriptions table
    if "webhook_subscriptions" not in existing_tables:
        op.create_table(
            "webhook_subscriptions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("endpoint_url", sa.String(length=500), nullable=False),
            sa.Column("secret", sa.String(length=255), nullable=False),
            sa.Column("event_types", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_webhook_subscriptions_is_active",
            "webhook_subscriptions",
            ["is_active"],
        )

    # 2. Add columns to outbox_events (idempotent: skip if column already exists)
    existing_outbox_cols = {c["name"] for c in inspector.get_columns("outbox_events")}

    if "endpoint_url" not in existing_outbox_cols:
        op.add_column(
            "outbox_events",
            sa.Column("endpoint_url", sa.String(length=500), nullable=True),
        )
    if "secret" not in existing_outbox_cols:
        op.add_column(
            "outbox_events", sa.Column("secret", sa.String(length=255), nullable=True)
        )
    if "endpoint_id" not in existing_outbox_cols:
        op.add_column(
            "outbox_events",
            sa.Column("endpoint_id", sa.String(length=100), nullable=True),
        )


def downgrade() -> None:
    # 1. Remove columns from outbox_events
    op.drop_column("outbox_events", "endpoint_id")
    op.drop_column("outbox_events", "secret")
    op.drop_column("outbox_events", "endpoint_url")

    # 2. Drop webhook_subscriptions table
    op.drop_index(
        "ix_webhook_subscriptions_is_active", table_name="webhook_subscriptions"
    )
    op.drop_table("webhook_subscriptions")
