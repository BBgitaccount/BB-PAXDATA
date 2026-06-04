"""merge c448 and bilateral trager heads

Revision ID: 20260602_merge
Revises: c448fa8484f5, 20260602_bt
Create Date: 2026-06-02 12:20:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260602_merge"
down_revision: str | tuple[str, str] | None = (
    "c448fa8484f5",
    "20260602_bt",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
