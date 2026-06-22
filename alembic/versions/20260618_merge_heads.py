"""merge_aevt_and_apvt_heads

Revision ID: 20260618_merge
Revises: 20260614_aevt, 20260618_apvt
Create Date: 2026-06-18 10:31:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260618_merge"
down_revision: str | Sequence[str] | None = ("20260614_aevt", "20260618_apvt")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
