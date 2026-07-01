"""add HITL formula validation v2: audit trail, RBAC, versioning

Revision ID: hitl_formula_v2_001
Revises: a07b04be8ec8
Create Date: 2026-05-31 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "hitl_formula_v2_001"
down_revision: str | None = "96c1d68338fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 0. SQLite workaround: drop dependent views before batch_alter_table ──
    # batch_alter_table renames the table, which fails if views reference it
    op.execute("DROP VIEW IF EXISTS v_formula_validation_results")

    bind = op.get_bind()
    is_current_default = (
        sa.text("true") if bind.dialect.name == "postgresql" else sa.text("1")
    )
    is_active_default = (
        sa.text("true") if bind.dialect.name == "postgresql" else sa.text("1")
    )

    # ── 1. Expand formula_validation_logs with HITL columns ────────────
    with op.batch_alter_table("formula_validation_logs", schema=None) as batch_op:
        # HITL verdict fields
        batch_op.add_column(sa.Column("human_review_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("human_verdict", sa.String(20), nullable=True))
        batch_op.add_column(
            sa.Column("human_corrected_value", sa.Float(), nullable=True)
        )
        batch_op.add_column(sa.Column("human_note", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("human_reviewed_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("human_reviewed_by", sa.String(100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("human_reviewer_role", sa.String(50), nullable=True)
        )

        # Versioning / immutability fields
        batch_op.add_column(
            sa.Column("log_version", sa.Integer(), nullable=True, server_default="1")
        )
        batch_op.add_column(sa.Column("superseded_by", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_current",
                sa.Boolean(),
                nullable=True,
                server_default=is_current_default,
            )
        )

        # Auto-triage fields
        batch_op.add_column(sa.Column("auto_triage_reason", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("confidence_at_review", sa.String(20), nullable=True)
        )

        # Optimistic locking fields
        batch_op.add_column(sa.Column("reviewer_id", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("locked_at", sa.DateTime(), nullable=True))

        # New indexes
        batch_op.create_index("idx_fval_is_current", ["is_current"], unique=False)
        batch_op.create_index("idx_fval_reviewer", ["reviewer_id"], unique=False)
        batch_op.create_index("idx_fval_human_verdict", ["human_verdict"], unique=False)

    # ── 1b. Recreate the dropped view ──────────────────────────────────
    op.execute("""
        CREATE VIEW v_formula_validation_results AS
        SELECT
            fvl.log_id,
            fvl.run_id,
            fvl.sentence_code,
            fvl.entity_type,
            fvl.entity_id,
            fvl.formula_name,
            fvl.expected_constraint,
            fvl.actual_value,
            fvl.status,
            fvl.details,
            fvl.created_at,
            fvl.human_verdict,
            fvl.human_corrected_value,
            fvl.is_current,
            fvl.log_version
        FROM formula_validation_logs fvl
        WHERE fvl.is_current
    """)

    # ── 2. Create formula_validation_audit (WORM) ──────────────────────
    op.create_table(
        "formula_validation_audit",
        sa.Column("audit_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("log_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("previous_verdict", sa.String(20), nullable=True),
        sa.Column("new_verdict", sa.String(20), nullable=True),
        sa.Column("previous_value", sa.Float(), nullable=True),
        sa.Column("new_value", sa.Float(), nullable=True),
        sa.Column("performed_by", sa.String(100), nullable=False),
        sa.Column(
            "performed_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("review_status", sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(
            ["log_id"],
            ["formula_validation_logs.log_id"],
        ),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    with op.batch_alter_table("formula_validation_audit", schema=None) as batch_op:
        batch_op.create_index("idx_faudit_log", ["log_id"], unique=False)
        batch_op.create_index("idx_faudit_action", ["action_type"], unique=False)
        batch_op.create_index("idx_faudit_performer", ["performed_by"], unique=False)
        batch_op.create_index("idx_faudit_at", ["performed_at"], unique=False)

    # ── 3. Create reviewer_assignments (RBAC) ──────────────────────────
    op.create_table(
        "reviewer_assignments",
        sa.Column("assignment_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("scope_type", sa.String(50), nullable=False),
        sa.Column("scope_value", sa.String(100), nullable=False),
        sa.Column("permission_level", sa.String(20), nullable=False),
        sa.Column(
            "max_daily_reviews", sa.Integer(), nullable=False, server_default="50"
        ),
        sa.Column(
            "current_daily_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "last_reset_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=is_active_default
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
        sa.UniqueConstraint(
            "reviewer_id", "scope_type", "scope_value", name="uq_reviewer_scope"
        ),
    )
    with op.batch_alter_table("reviewer_assignments", schema=None) as batch_op:
        batch_op.create_index("idx_rassign_reviewer", ["reviewer_id"], unique=False)
        batch_op.create_index(
            "idx_rassign_scope", ["scope_type", "scope_value"], unique=False
        )


def downgrade() -> None:
    # Drop reviewer_assignments
    with op.batch_alter_table("reviewer_assignments", schema=None) as batch_op:
        batch_op.drop_index("idx_rassign_scope")
        batch_op.drop_index("idx_rassign_reviewer")
    op.drop_table("reviewer_assignments")

    # Drop formula_validation_audit
    with op.batch_alter_table("formula_validation_audit", schema=None) as batch_op:
        batch_op.drop_index("idx_faudit_at")
        batch_op.drop_index("idx_faudit_performer")
        batch_op.drop_index("idx_faudit_action")
        batch_op.drop_index("idx_faudit_log")
    op.drop_table("formula_validation_audit")

    # Remove new columns from formula_validation_logs
    with op.batch_alter_table("formula_validation_logs", schema=None) as batch_op:
        batch_op.drop_index("idx_fval_human_verdict")
        batch_op.drop_index("idx_fval_reviewer")
        batch_op.drop_index("idx_fval_is_current")
        batch_op.drop_column("locked_at")
        batch_op.drop_column("reviewer_id")
        batch_op.drop_column("confidence_at_review")
        batch_op.drop_column("auto_triage_reason")
        batch_op.drop_column("is_current")
        batch_op.drop_column("superseded_by")
        batch_op.drop_column("log_version")
        batch_op.drop_column("human_reviewer_role")
        batch_op.drop_column("human_reviewed_by")
        batch_op.drop_column("human_reviewed_at")
        batch_op.drop_column("human_note")
        batch_op.drop_column("human_corrected_value")
        batch_op.drop_column("human_verdict")
        batch_op.drop_column("human_review_id")
