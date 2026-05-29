"""add_v_formula_validation_results

Revision ID: 313083ab4704
Revises: a07b04be8ec8
Create Date: 2026-05-26 15:02:42.506939

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "313083ab4704"
down_revision: Union[str, None] = "a07b04be8ec8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW v_formula_validation_results AS
        SELECT 
            f.log_id,
            f.run_id,
            f.entity_type,
            f.entity_id,
            f.formula_name,
            f.expected_constraint,
            f.actual_value,
            f.status,
            f.details,
            COALESCE(s.text, seg.text) AS text,
            COALESCE(s.speaker_name, seg.speaker_name) AS speaker_name,
            COALESCE(s.country, seg.country) AS country,
            COALESCE(s.panel_id, seg.panel_id) AS panel_id,
            f.created_at
        FROM formula_validation_logs f
        LEFT JOIN sentences s ON f.entity_type = 'sentence' AND f.entity_id = s.sent_id
        LEFT JOIN segments seg ON f.entity_type = 'segment' AND f.entity_id = seg.seg_id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_formula_validation_results")
