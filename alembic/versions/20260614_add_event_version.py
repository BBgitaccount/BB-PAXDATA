"""add_event_version_to_outbox

Revision ID: 20260614_aevt
Revises: 20260614_rlmt
Create Date: 2026-06-14 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260614_aevt"
down_revision: str | Sequence[str] | None = "20260614_rlmt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Add event_version column to outbox_events (if not exists)
    outbox_cols = {c["name"] for c in inspector.get_columns("outbox_events")}
    if "event_version" not in outbox_cols:
        op.add_column(
            "outbox_events",
            sa.Column(
                "event_version", sa.Integer(), server_default="1", nullable=False
            ),
        )

    # 2. Add event_version column to dead_letter_events (if table & column exist)
    existing_tables = inspector.get_table_names()
    if "dead_letter_events" in existing_tables:
        dle_cols = {c["name"] for c in inspector.get_columns("dead_letter_events")}
        if "event_version" not in dle_cols:
            op.add_column(
                "dead_letter_events",
                sa.Column(
                    "event_version", sa.Integer(), server_default="1", nullable=False
                ),
            )


def downgrade() -> None:
    op.drop_column("dead_letter_events", "event_version")
    op.drop_column("outbox_events", "event_version")
