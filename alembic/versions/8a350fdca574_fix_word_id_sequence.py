"""fix_word_id_sequence

Revision ID: 8a350fdca574
Revises: 20260618_merge
Create Date: 2026-06-19 01:11:29.674767

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a350fdca574"
down_revision: str | None = "20260618_merge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            "CREATE TEMP TABLE words_temp AS SELECT * FROM words ORDER BY word_id;"
        )
        op.execute("TRUNCATE words RESTART IDENTITY CASCADE;")
        op.execute(
            """
            INSERT INTO words (sent_id, seg_id, file_id, speaker_id, speaker_name, country, bloc, power_level, word_raw, word_norm, word_position, is_stopword, diplo_score, is_named_entity)
            SELECT sent_id, seg_id, file_id, speaker_id, speaker_name, country, bloc, power_level, word_raw, word_norm, word_position, is_stopword, diplo_score, is_named_entity
            FROM words_temp ORDER BY word_id;
        """
        )
        op.execute("DROP TABLE words_temp;")
    else:
        op.execute(
            "CREATE TEMP TABLE words_temp AS SELECT * FROM words ORDER BY word_id;"
        )
        op.execute("DELETE FROM words;")
        # Check if sqlite_sequence exists before deleting
        has_sqlite_sequence = (
            bind.execute(
                sa.text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
                )
            ).first()
            is not None
        )
        if has_sqlite_sequence:
            op.execute("DELETE FROM sqlite_sequence WHERE name = 'words';")
        op.execute(
            """
            INSERT INTO words (sent_id, seg_id, file_id, speaker_id, speaker_name, country, bloc, power_level, word_raw, word_norm, word_position, is_stopword, diplo_score, is_named_entity)
            SELECT sent_id, seg_id, file_id, speaker_id, speaker_name, country, bloc, power_level, word_raw, word_norm, word_position, is_stopword, diplo_score, is_named_entity
            FROM words_temp ORDER BY word_id;
        """
        )
        op.execute("DROP TABLE words_temp;")


def downgrade() -> None:
    pass
