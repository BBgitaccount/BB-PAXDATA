"""add_sentence_code

Revision ID: f904f26a70c1
Revises: fix_tm_composite_pk
Create Date: 2026-05-30 02:28:18.199157

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import NoSuchTableError

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f904f26a70c1"
down_revision: str | None = "fix_tm_composite_pk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def add_column_safely(
    table_name: str,
    column_name: str,
    col_type,
    index_name: str | None = None,
    unique: bool = False,
    constraint_name: str | None = None,
) -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        if table_name == "ai_human_review_queue":
            flagged_at_default = (
                sa.text("CURRENT_TIMESTAMP")
                if conn.dialect.name == "postgresql"
                else sa.text("datetime('now')")
            )
            op.create_table(
                "ai_human_review_queue",
                sa.Column(
                    "review_id", sa.Integer(), primary_key=True, autoincrement=True
                ),
                sa.Column("sent_id", sa.String(), nullable=False),
                sa.Column("sentence_code", sa.String(length=50), nullable=True),
                sa.Column("seg_id", sa.Text(), nullable=True),
                sa.Column("file_id", sa.Text(), nullable=True),
                sa.Column("speaker_name", sa.Text(), nullable=True),
                sa.Column("country", sa.Text(), nullable=True),
                sa.Column("trigger_type", sa.String(), nullable=False),
                sa.Column("ai_risk_score", sa.Integer(), nullable=True),
                sa.Column("anomaly_types", sa.Text(), nullable=True),
                sa.Column("uncertainty_score", sa.Integer(), nullable=True),
                sa.Column(
                    "status",
                    sa.String(),
                    server_default=sa.text("'PENDING'"),
                    nullable=True,
                ),
                sa.Column("assigned_to", sa.Text(), nullable=True),
                sa.Column("reviewer_notes", sa.Text(), nullable=True),
                sa.Column("original_ai_json", sa.Text(), nullable=False),
                sa.Column("corrected_json", sa.Text(), nullable=True),
                sa.Column(
                    "flagged_at",
                    sa.Text(),
                    server_default=flagged_at_default,
                    nullable=True,
                ),
                sa.Column("reviewed_at", sa.Text(), nullable=True),
                sa.Column("review_duration_sec", sa.Integer(), nullable=True),
            )
            op.create_index("idx_review_status", "ai_human_review_queue", ["status"])
            op.create_index("idx_review_file", "ai_human_review_queue", ["file_id"])
            if index_name:
                op.create_index(index_name, "ai_human_review_queue", [column_name])
            return
        else:
            raise NoSuchTableError(table_name)

    columns = [c["name"] for c in inspector.get_columns(table_name)]
    if column_name not in columns:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column(column_name, col_type, nullable=True))
            if index_name:
                batch_op.create_index(index_name, [column_name], unique=False)
            if unique and constraint_name:
                batch_op.create_unique_constraint(constraint_name, [column_name])


def drop_column_safely(
    table_name: str,
    column_name: str,
    index_name: str | None = None,
    constraint_name: str | None = None,
) -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    if column_name in columns:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            if constraint_name:
                batch_op.drop_constraint(constraint_name, type_="unique")
            if index_name:
                batch_op.drop_index(index_name)
            batch_op.drop_column(column_name)


def upgrade() -> None:
    # Disable SQLite view and foreign key checks during alterations
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA legacy_alter_table = ON")
        op.execute("PRAGMA foreign_keys = OFF")

    # Drop view first to avoid issues with schema alterations
    op.execute("DROP VIEW IF EXISTS v_formula_validation_results")

    # Safe additions
    add_column_safely(
        "ai_contextual_flags",
        "sentence_code",
        sa.String(length=50),
        "idx_flags_sentence_code",
    )
    add_column_safely(
        "ai_fail_analysis",
        "sentence_code",
        sa.String(length=50),
        "idx_fail_sentence_code",
    )
    add_column_safely(
        "ai_human_review_queue",
        "sentence_code",
        sa.String(length=50),
        "idx_review_sentence_code",
    )
    add_column_safely(
        "ai_sentence_analysis",
        "sentence_code",
        sa.String(length=50),
        "idx_ai_sentence_code",
    )
    add_column_safely(
        "ai_validation_log",
        "sentence_code",
        sa.String(length=50),
        "idx_val_sentence_code",
    )
    add_column_safely(
        "formula_validation_logs",
        "sentence_code",
        sa.String(length=50),
        "idx_fval_sentence_code",
    )
    add_column_safely(
        "sentences",
        "sentence_code",
        sa.String(length=50),
        "idx_sent_code",
        unique=True,
        constraint_name="uq_sentence_code",
    )

    # Apply batch alter on country_stats safely if needed
    try:
        with op.batch_alter_table("country_stats", schema=None) as batch_op:
            batch_op.alter_column(
                "n_segments",
                existing_type=sa.INTEGER(),
                server_default=None,
                existing_nullable=False,
            )
            batch_op.alter_column(
                "n_sentences",
                existing_type=sa.INTEGER(),
                server_default=None,
                existing_nullable=False,
            )
            batch_op.alter_column(
                "total_words",
                existing_type=sa.INTEGER(),
                server_default=None,
                existing_nullable=False,
            )
            batch_op.alter_column(
                "total_duration_sec",
                existing_type=sa.INTEGER(),
                server_default=None,
                existing_nullable=False,
            )
    except Exception:
        pass

    # Recreate view with sentence_code
    op.execute(
        """
        CREATE VIEW v_formula_validation_results AS
        SELECT 
            f.log_id,
            f.run_id,
            f.entity_type,
            f.entity_id,
            f.sentence_code,
            f.formula_name,
            f.expected_constraint,
            f.actual_value,
            f.status,
            f.details,
            COALESCE(s.text, seg.text) AS text,
            COALESCE(s.speaker_name, seg.speaker_name) AS speaker_name,
            COALESCE(s.country, seg.country) AS country,
            COALESCE(s.file_id, seg.file_id) AS file_id,
            f.created_at
        FROM formula_validation_logs f
        LEFT JOIN sentences s ON f.entity_type = 'sentence' AND f.entity_id = s.sent_id
        LEFT JOIN segments seg ON f.entity_type = 'segment' AND f.entity_id = seg.seg_id
        """
    )

    # Re-enable SQLite checks
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA legacy_alter_table = OFF")
        op.execute("PRAGMA foreign_keys = ON")


def downgrade() -> None:
    # Disable SQLite view and foreign key checks during alterations
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA legacy_alter_table = ON")
        op.execute("PRAGMA foreign_keys = OFF")

    # Drop view first to avoid issues with schema alterations
    op.execute("DROP VIEW IF EXISTS v_formula_validation_results")

    # Safe drops
    drop_column_safely(
        "sentences", "sentence_code", "idx_sent_code", "uq_sentence_code"
    )
    drop_column_safely(
        "formula_validation_logs", "sentence_code", "idx_fval_sentence_code"
    )
    drop_column_safely("ai_validation_log", "sentence_code", "idx_val_sentence_code")
    drop_column_safely("ai_sentence_analysis", "sentence_code", "idx_ai_sentence_code")
    drop_column_safely(
        "ai_human_review_queue", "sentence_code", "idx_review_sentence_code"
    )
    drop_column_safely("ai_fail_analysis", "sentence_code", "idx_fail_sentence_code")
    drop_column_safely(
        "ai_contextual_flags", "sentence_code", "idx_flags_sentence_code"
    )

    try:
        with op.batch_alter_table("country_stats", schema=None) as batch_op:
            batch_op.alter_column(
                "total_duration_sec",
                existing_type=sa.INTEGER(),
                server_default=sa.text("'0'"),
                existing_nullable=False,
            )
            batch_op.alter_column(
                "total_words",
                existing_type=sa.INTEGER(),
                server_default=sa.text("'0'"),
                existing_nullable=False,
            )
            batch_op.alter_column(
                "n_sentences",
                existing_type=sa.INTEGER(),
                server_default=sa.text("'0'"),
                existing_nullable=False,
            )
            batch_op.alter_column(
                "n_segments",
                existing_type=sa.INTEGER(),
                server_default=sa.text("'0'"),
                existing_nullable=False,
            )
    except Exception:
        pass

    # Recreate view without sentence_code
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
            COALESCE(s.file_id, seg.file_id) AS file_id,
            f.created_at
        FROM formula_validation_logs f
        LEFT JOIN sentences s ON f.entity_type = 'sentence' AND f.entity_id = s.sent_id
        LEFT JOIN segments seg ON f.entity_type = 'segment' AND f.entity_id = seg.seg_id
        """
    )

    # Re-enable SQLite checks
    if bind.dialect.name == "sqlite":
        op.execute("PRAGMA legacy_alter_table = OFF")
        op.execute("PRAGMA foreign_keys = ON")
