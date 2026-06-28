"""merge_all_heads

Revision ID: 76e43050d086
Revises: 20260624_add_retrain_shadow, 20260625_add_weight_calibration, add_notification, add_scheduled_reports_tables, bb4a989f268f
Create Date: 2026-06-26 18:37:26.099318

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "76e43050d086"
down_revision: str | None = (
    "20260624_add_retrain_shadow",
    "20260625_add_weight_calibration",
    "add_notification",
    "add_scheduled_reports_tables",
    "bb4a989f268f",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
