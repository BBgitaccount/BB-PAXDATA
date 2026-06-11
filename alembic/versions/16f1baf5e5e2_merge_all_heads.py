"""merge_all_heads

Revision ID: 16f1baf5e5e2
Revises: add_topic_diversity, bloat5_add_demand_analysis, perf_1_gat_binary
Create Date: 2026-06-10 06:11:36.423874

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "16f1baf5e5e2"
down_revision: str | Sequence[str] | None = (
    "add_topic_diversity",
    "bloat5_add_demand_analysis",
    "perf_1_gat_binary",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
