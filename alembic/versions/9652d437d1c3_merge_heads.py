"""merge_heads

Revision ID: 9652d437d1c3
Revises: 20260512_add_quality_assurance_tables, 7b0a258705f4
Create Date: 2026-05-15 14:45:44.058914

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9652d437d1c3"
down_revision: str | None = (
    "20260512_add_quality_assurance_tables",
    "7b0a258705f4",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
