"""add_human_reviews_and_calibration_reports

Revision ID: b754aee19e42
Revises: 44785eb5dced
Create Date: 2026-05-18 14:30:05.594843

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b754aee19e42"
down_revision: str | None = "44785eb5dced"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create actor_action_matrix
    op.create_table(
        "actor_action_matrix",
        sa.Column("matrix_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("panel_id", sa.String(), nullable=False),
        sa.Column("from_country", sa.Text(), nullable=False),
        sa.Column("to_country", sa.Text(), nullable=False),
        sa.Column("verb", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("avg_sentiment", sa.Float(), nullable=False),
        sa.Column("is_passive_pct", sa.Float(), nullable=False),
        sa.Column("is_negative_pct", sa.Float(), nullable=False),
        sa.Column(
            "last_updated",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("matrix_id"),
    )
    with op.batch_alter_table("actor_action_matrix", schema=None) as batch_op:
        batch_op.create_index("idx_matrix_from", ["from_country"], unique=False)
        batch_op.create_index("idx_matrix_panel", ["panel_id"], unique=False)
        batch_op.create_index("idx_matrix_to", ["to_country"], unique=False)

    # 2. Create ai_explanations
    op.create_table(
        "ai_explanations",
        sa.Column("explanation_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sent_id", sa.String(), nullable=False),
        sa.Column("risk_explanation", sa.Text(), nullable=False),
        sa.Column("sentiment_explanation", sa.Text(), nullable=False),
        sa.Column("grammatical_explanation", sa.Text(), nullable=True),
        sa.Column("discrepancy_explanation", sa.Text(), nullable=True),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("token_attributions_json", sa.Text(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("explanation_id"),
    )
    with op.batch_alter_table("ai_explanations", schema=None) as batch_op:
        batch_op.create_index("idx_exp_sent", ["sent_id"], unique=False)

    # 3. Create calibration_reports
    op.create_table(
        "calibration_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("evaluation_period_start", sa.DateTime(), nullable=False),
        sa.Column("evaluation_period_end", sa.DateTime(), nullable=False),
        sa.Column("cohens_kappa_frame", sa.Float(), nullable=True),
        sa.Column("cohens_kappa_risk", sa.Float(), nullable=True),
        sa.Column("ai_human_f1_frame", sa.Float(), nullable=True),
        sa.Column("ai_human_f1_risk", sa.Float(), nullable=True),
        sa.Column("sbi_mae", sa.Float(), nullable=True),
        sa.Column("total_reviews", sa.Integer(), nullable=False),
        sa.Column("total_disagreements", sa.Integer(), nullable=False),
        sa.Column(
            "top_disagreement_patterns",
            sa.JSON(),
            nullable=True,
            comment="En sık anlaşmazlık patternları listesi",
        ),
        sa.Column("requires_prompt_update", sa.Boolean(), nullable=False),
        sa.Column("requires_weight_update", sa.Boolean(), nullable=False),
        sa.Column("alert_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("calibration_reports", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_calibration_reports_prompt_version"),
            ["prompt_version"],
            unique=False,
        )

    # 4. Create dependency_triples
    op.create_table(
        "dependency_triples",
        sa.Column("triple_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sent_id", sa.String(), nullable=False),
        sa.Column("seg_id", sa.String(), nullable=True),
        sa.Column("panel_id", sa.String(), nullable=True),
        sa.Column("speaker_name", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("subject_raw", sa.Text(), nullable=True),
        sa.Column("subject_resolved", sa.Text(), nullable=True),
        sa.Column("verb_lemma", sa.Text(), nullable=True),
        sa.Column("object_raw", sa.Text(), nullable=True),
        sa.Column("object_resolved", sa.Text(), nullable=True),
        sa.Column("is_passive", sa.Integer(), nullable=False),
        sa.Column("is_negative", sa.Integer(), nullable=False),
        sa.Column("sentiment_context", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("human_verified", sa.Integer(), nullable=False),
        sa.Column("verification_status", sa.Text(), nullable=False),
        sa.Column(
            "extracted_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("triple_id"),
    )
    with op.batch_alter_table("dependency_triples", schema=None) as batch_op:
        batch_op.create_index("idx_dep_from", ["subject_resolved"], unique=False)
        batch_op.create_index("idx_dep_panel", ["panel_id"], unique=False)
        batch_op.create_index("idx_dep_sent", ["sent_id"], unique=False)
        batch_op.create_index("idx_dep_to", ["object_resolved"], unique=False)
        batch_op.create_index("idx_dep_verb", ["verb_lemma"], unique=False)

    # 5. Create human_reviews
    op.create_table(
        "human_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "analysis_id",
            sa.String(length=36),
            nullable=False,
            comment="FK -> ai_sentence_analyses.id",
        ),
        sa.Column("reviewer_id", sa.String(length=100), nullable=False),
        sa.Column("ai_sbi_score", sa.Float(), nullable=True),
        sa.Column("ai_dominant_frame", sa.String(length=100), nullable=True),
        sa.Column("ai_risk_level", sa.String(length=20), nullable=True),
        sa.Column("ai_sentiment_score", sa.Float(), nullable=True),
        sa.Column("human_sbi_score", sa.Float(), nullable=True),
        sa.Column("human_dominant_frame", sa.String(length=100), nullable=True),
        sa.Column("human_risk_level", sa.String(length=20), nullable=True),
        sa.Column("human_sentiment_score", sa.Float(), nullable=True),
        sa.Column("agreement_status", sa.String(length=20), nullable=False),
        sa.Column("disagreement_reason", sa.Text(), nullable=True),
        sa.Column("review_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("has_frame_disagreement", sa.Boolean(), nullable=True),
        sa.Column("has_risk_disagreement", sa.Boolean(), nullable=True),
        sa.Column("sbi_delta", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("human_reviews", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_human_reviews_analysis_id"), ["analysis_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_human_reviews_reviewer_id"), ["reviewer_id"], unique=False
        )

    # 6. Create discourse_network_edges_legacy
    op.create_table(
        "discourse_network_edges_legacy",
        sa.Column("edge_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("panel_id", sa.String(), nullable=True),
        sa.Column("from_country", sa.Text(), nullable=False),
        sa.Column("to_country", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("avg_sentiment", sa.Float(), nullable=False),
        sa.Column("edge_type", sa.Text(), nullable=True),
        sa.Column("power_source", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["panel_id"],
            ["panels.panel_id"],
        ),
        sa.PrimaryKeyConstraint("edge_id"),
    )
    with op.batch_alter_table(
        "discourse_network_edges_legacy", schema=None
    ) as batch_op:
        batch_op.create_index("idx_net_legacy_from", ["from_country"], unique=False)

    # 7. Drop risk_events if it exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if "risk_events" in tables:
        with op.batch_alter_table("risk_events", schema=None) as batch_op:
            batch_op.drop_index("idx_risk_country")
        op.drop_table("risk_events")

    # 8. Recreate v_f_fail_network_context using discourse_network_edges_legacy
    op.execute("DROP VIEW IF EXISTS v_f_fail_network_context")
    op.execute(
        """
    CREATE VIEW v_f_fail_network_context AS
    SELECT
        f.sent_id, f.speaker_name, f.country, f.check_type,
        dne.from_country, dne.to_country, dne.edge_type,
        cp.relationship_type, cp.affinity_score,
        f.fail_reason AS AI_Neden_Fail
    FROM ai_fail_analysis f
    LEFT JOIN sentences s ON f.sent_id = s.sent_id
    LEFT JOIN discourse_network_edges_legacy dne
        ON s.panel_id = dne.panel_id AND s.country = dne.from_country
    LEFT JOIN country_pair_sentiment cp
        ON dne.from_country = cp.from_country AND dne.to_country = cp.to_country
    WHERE f.country NOT IN ('—','Unknown')
    """
    )


def downgrade() -> None:
    # Drop view first
    op.execute("DROP VIEW IF EXISTS v_f_fail_network_context")

    # 1. Drop discourse_network_edges_legacy
    with op.batch_alter_table(
        "discourse_network_edges_legacy", schema=None
    ) as batch_op:
        batch_op.drop_index("idx_net_legacy_from")
    op.drop_table("discourse_network_edges_legacy")

    # 2. Drop human_reviews
    with op.batch_alter_table("human_reviews", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_human_reviews_reviewer_id"))
        batch_op.drop_index(batch_op.f("ix_human_reviews_analysis_id"))
    op.drop_table("human_reviews")

    # 3. Drop dependency_triples
    with op.batch_alter_table("dependency_triples", schema=None) as batch_op:
        batch_op.drop_index("idx_dep_verb")
        batch_op.drop_index("idx_dep_to")
        batch_op.drop_index("idx_dep_sent")
        batch_op.drop_index("idx_dep_panel")
        batch_op.drop_index("idx_dep_from")
    op.drop_table("dependency_triples")

    # 4. Drop calibration_reports
    with op.batch_alter_table("calibration_reports", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_calibration_reports_prompt_version"))
    op.drop_table("calibration_reports")

    # 5. Drop ai_explanations
    with op.batch_alter_table("ai_explanations", schema=None) as batch_op:
        batch_op.drop_index("idx_exp_sent")
    op.drop_table("ai_explanations")

    # 6. Drop actor_action_matrix
    with op.batch_alter_table("actor_action_matrix", schema=None) as batch_op:
        batch_op.drop_index("idx_matrix_to")
        batch_op.drop_index("idx_matrix_panel")
        batch_op.drop_index("idx_matrix_from")
    op.drop_table("actor_action_matrix")

    # 7. Recreate risk_events if rollback occurs
    op.create_table(
        "risk_events",
        sa.Column("risk_id", sa.INTEGER(), nullable=False),
        sa.Column("panel_id", sa.VARCHAR(), nullable=True),
        sa.Column("seg_id", sa.VARCHAR(), nullable=True),
        sa.Column("sent_id", sa.TEXT(), nullable=True),
        sa.Column("from_country", sa.TEXT(), nullable=True),
        sa.Column("speaker_name", sa.TEXT(), nullable=True),
        sa.Column("power_level", sa.INTEGER(), nullable=False),
        sa.Column("signal_phrase", sa.TEXT(), nullable=True),
        sa.Column("target_country", sa.TEXT(), nullable=True),
        sa.Column("severity", sa.INTEGER(), nullable=True),
        sa.Column("context", sa.TEXT(), nullable=True),
        sa.ForeignKeyConstraint(
            ["panel_id"],
            ["panels.panel_id"],
        ),
        sa.ForeignKeyConstraint(
            ["seg_id"],
            ["segments.seg_id"],
        ),
        sa.PrimaryKeyConstraint("risk_id"),
    )
    with op.batch_alter_table("risk_events", schema=None) as batch_op:
        batch_op.create_index("idx_risk_country", ["from_country"], unique=False)

    # ### end Alembic commands ###
