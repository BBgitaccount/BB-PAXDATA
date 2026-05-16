"""faz5_manual_topic_additions

Revision ID: 1ef902da8b4f
Revises: faz4_network_dyadic_2026
Create Date: 2026-05-16 04:03:17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ef902da8b4f"
down_revision: str | None = "faz4_network_dyadic_2026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Check if table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. TopicAssignmentORM tablosunu oluştur (eğer yoksa)
    if "topic_assignments" not in tables:
        op.create_table(
            "topic_assignments",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("segment_id", sa.String(length=64), nullable=False),
            sa.Column("analysis_id", sa.String(length=64), nullable=False),
            sa.Column("primary_topic", sa.String(length=64), nullable=False),
            sa.Column("topic_scores", sa.JSON(), nullable=False),
            sa.Column("topic_label", sa.String(length=255), nullable=True),
            sa.Column("ctfidf_keywords", sa.JSON(), nullable=False),
            sa.Column("model_metadata", sa.JSON(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_topic_assignments_analysis_id",
            "topic_assignments",
            ["analysis_id"],
            unique=False,
        )
        op.create_index(
            "ix_topic_assignments_segment_id",
            "topic_assignments",
            ["segment_id"],
            unique=False,
        )

    # 2. transcripts ve analytics tablolarını oluştur (eğer yoksa)
    if "transcripts" not in tables:
        op.create_table(
            "transcripts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("speaker_name", sa.String(length=255), nullable=False),
            sa.Column("country_code", sa.String(length=10), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=True),
            sa.Column("vader_compound", sa.Float(), nullable=True),
            sa.Column("power_level", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "analytics" not in tables:
        op.create_table(
            "analytics",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("transcript_id", sa.Integer(), nullable=False),
            sa.Column("sbi_score", sa.Float(), nullable=True),
            sa.Column("dki_score", sa.Float(), nullable=True),
            sa.Column("hedging_markers", sa.JSON(), nullable=False),
            sa.Column("framing_labels", sa.JSON(), nullable=False),
            sa.Column("raw_ai_output", sa.Text(), nullable=True),
            sa.Column("topic_scores", sa.JSON(), nullable=True),
            sa.Column("topic_node_mapping", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(
                ["transcript_id"],
                ["transcripts.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        # 3. AnalyticModel'e yeni kolonları ekle (eğer yoksa)
        columns = [c["name"] for c in inspector.get_columns("analytics")]
        with op.batch_alter_table("analytics", schema=None) as batch_op:
            if "topic_scores" not in columns:
                batch_op.add_column(sa.Column("topic_scores", sa.JSON(), nullable=True))
            if "topic_node_mapping" not in columns:
                batch_op.add_column(
                    sa.Column("topic_node_mapping", sa.JSON(), nullable=True)
                )


def downgrade() -> None:
    with op.batch_alter_table("analytics", schema=None) as batch_op:
        batch_op.drop_column("topic_node_mapping")
        batch_op.drop_column("topic_scores")

    op.drop_index("ix_topic_assignments_segment_id", table_name="topic_assignments")
    op.drop_index("ix_topic_assignments_analysis_id", table_name="topic_assignments")
    op.drop_table("topic_assignments")
