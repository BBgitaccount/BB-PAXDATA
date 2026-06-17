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
    # Drop all dependent views first (CASCADE handles transitive dependencies)
    op.execute("DROP VIEW IF EXISTS v_f_fail_network_context CASCADE")
    op.execute("DROP VIEW IF EXISTS v_transcript_summary CASCADE")
    op.execute("DROP VIEW IF EXISTS v_analytics_summary CASCADE")

    # Drop legacy tables with CASCADE to handle any remaining FK/view dependencies
    op.execute("DROP TABLE IF EXISTS transcripts CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics CASCADE")
    op.execute("DROP TABLE IF EXISTS discourse_network_edges_legacy CASCADE")
    op.execute("DROP TABLE IF EXISTS legacy_country_references CASCADE")


def downgrade() -> None:
    pass
