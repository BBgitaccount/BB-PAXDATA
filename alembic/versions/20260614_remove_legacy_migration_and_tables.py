"""remove_legacy_migration_and_tables

Revision ID: 20260614_rlmt
Revises: 20260613_awof
Create Date: 2026-06-14 03:57:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260614_rlmt"
down_revision: str | Sequence[str] | None = "20260613_awof"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    cascade = "" if is_sqlite else " CASCADE"

    # Drop all dependent views first
    op.execute(f"DROP VIEW IF EXISTS v_f_fail_network_context{cascade}")
    op.execute(f"DROP VIEW IF EXISTS v_transcript_summary{cascade}")
    op.execute(f"DROP VIEW IF EXISTS v_analytics_summary{cascade}")

    # Drop legacy tables
    op.execute(f"DROP TABLE IF EXISTS transcripts{cascade}")
    op.execute(f"DROP TABLE IF EXISTS analytics{cascade}")
    op.execute(f"DROP TABLE IF EXISTS discourse_network_edges_legacy{cascade}")
    op.execute(f"DROP TABLE IF EXISTS legacy_country_references{cascade}")


def downgrade() -> None:
    pass
