"""add_topic_matrix_2_0_tables

Revision ID: 96c1d68338fa
Revises: f904f26a70c1
Create Date: 2026-05-30 02:56:19.912446

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "96c1d68338fa"
down_revision: Union[str, None] = "f904f26a70c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Add columns to topic_matrix
    with op.batch_alter_table("topic_matrix", schema=None) as batch_op:
        columns_to_add = [
            ("mention_count", sa.Integer()),
            ("avg_sentiment", sa.Float()),
            ("risk_score", sa.Float()),
            ("demand_count", sa.Integer()),
            ("dominant_emotion", sa.Text()),
            ("dominant_frame", sa.Text()),
        ]
        existing_cols = [c["name"] for c in inspector.get_columns("topic_matrix")]
        for name, type_ in columns_to_add:
            if name not in existing_cols:
                batch_op.add_column(sa.Column(name, type_, nullable=True))

    # 2. Add column to topic_matrices
    if "topic_matrices" in tables:
        existing_cols = [c["name"] for c in inspector.get_columns("topic_matrices")]
        if "topic_details" not in existing_cols:
            with op.batch_alter_table("topic_matrices", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column("topic_details", sa.JSON(), nullable=True)
                )

    # 3. Create new tables
    if "segment_events" not in tables:
        op.create_table(
            "segment_events",
            sa.Column("event_id", sa.String(length=36), nullable=False),
            sa.Column("event_timestamp", sa.DateTime(), nullable=False),
            sa.Column("file_id", sa.String(length=255), nullable=False),
            sa.Column("segment_id", sa.String(length=255), nullable=False),
            sa.Column("country", sa.String(length=100), nullable=False),
            sa.Column("text_snippet", sa.Text(), nullable=True),
            sa.Column("vader_compound", sa.Float(), nullable=False),
            sa.Column("diplo_compound", sa.Float(), nullable=False),
            sa.Column("vad_vector", sa.JSON(), nullable=True),
            sa.Column("emotion_category", sa.String(length=50), nullable=True),
            sa.Column("risk_score", sa.Float(), nullable=False),
            sa.Column("demand_count", sa.Integer(), nullable=False),
            sa.Column("speech_act", sa.String(length=50), nullable=True),
            sa.Column("hedging_score", sa.Float(), nullable=False),
            sa.Column("politeness_ratio", sa.Float(), nullable=False),
            sa.Column("topic_scores", sa.JSON(), nullable=False),
            sa.Column("topic_model_version", sa.String(length=50), nullable=False),
            sa.Column("frame_distribution", sa.JSON(), nullable=True),
            sa.Column("pipeline_run_id", sa.String(length=36), nullable=False),
            sa.PrimaryKeyConstraint("event_id"),
        )
        with op.batch_alter_table("segment_events", schema=None) as batch_op:
            batch_op.create_index(
                "ix_events_file_country", ["file_id", "country"], unique=False
            )
            batch_op.create_index(
                "ix_events_pipeline_run", ["pipeline_run_id"], unique=False
            )

    if "actor_topic_projection" not in tables:
        op.create_table(
            "actor_topic_projection",
            sa.Column("file_id", sa.String(length=255), nullable=False),
            sa.Column("country", sa.String(length=100), nullable=False),
            sa.Column("topic", sa.String(length=200), nullable=False),
            sa.Column("topic_model_version", sa.String(length=50), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("mention_count", sa.Integer(), nullable=False),
            sa.Column("fuzzy_mention_mass", sa.Float(), nullable=False),
            sa.Column("avg_sentiment", sa.Float(), nullable=False),
            sa.Column("sentiment_ci_lower", sa.Float(), nullable=True),
            sa.Column("sentiment_ci_upper", sa.Float(), nullable=True),
            sa.Column("sentiment_std", sa.Float(), nullable=True),
            sa.Column("risk_score", sa.Float(), nullable=False),
            sa.Column("risk_ci_lower", sa.Float(), nullable=True),
            sa.Column("risk_ci_upper", sa.Float(), nullable=True),
            sa.Column("composite_risk_index", sa.Float(), nullable=True),
            sa.Column("demand_count", sa.Float(), nullable=False),
            sa.Column("demand_density_per_1k", sa.Float(), nullable=True),
            sa.Column("speech_act_distribution", sa.JSON(), nullable=True),
            sa.Column("avg_vad", sa.JSON(), nullable=True),
            sa.Column("dominant_emotion", sa.String(length=50), nullable=True),
            sa.Column("frame_distribution", sa.JSON(), nullable=True),
            sa.Column("dominant_frame", sa.String(length=50), nullable=True),
            sa.Column("frame_competition_index", sa.Float(), nullable=True),
            sa.Column("avg_hedging", sa.Float(), nullable=True),
            sa.Column("avg_politeness", sa.Float(), nullable=True),
            sa.Column("diplomatic_signal_index", sa.Float(), nullable=True),
            sa.Column("topic_entropy", sa.Float(), nullable=True),
            sa.Column("js_divergence", sa.Float(), nullable=True),
            sa.Column("top_coalition_actors", sa.JSON(), nullable=True),
            sa.Column("last_event_id", sa.String(length=36), nullable=False),
            sa.Column("segment_count", sa.Integer(), nullable=False),
            sa.Column("total_word_count", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint(
                "file_id", "country", "topic", "topic_model_version"
            ),
        )
        with op.batch_alter_table("actor_topic_projection", schema=None) as batch_op:
            batch_op.create_index(
                "ix_proj_file_country", ["file_id", "country"], unique=False
            )
            batch_op.create_index(
                "ix_proj_topic_version", ["topic", "topic_model_version"], unique=False
            )

    if "actor_topic_documents" not in tables:
        op.create_table(
            "actor_topic_documents",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("file_id", sa.String(length=255), nullable=False),
            sa.Column("country", sa.String(length=100), nullable=False),
            sa.Column("topic_model_version", sa.String(length=50), nullable=False),
            sa.Column("topic_details", sa.JSON(), nullable=False),
            sa.Column("network_edges", sa.JSON(), nullable=True),
            sa.Column("diplomatic_tension_index", sa.Float(), nullable=True),
            sa.Column("agenda_diversity_index", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("actor_topic_documents", schema=None) as batch_op:
            batch_op.create_index(
                "ix_actor_topic_documents_country", ["country"], unique=False
            )
            batch_op.create_index(
                "ix_actor_topic_documents_file_id", ["file_id"], unique=False
            )

    if "aggregation_lineage" not in tables:
        op.create_table(
            "aggregation_lineage",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("projection_id", sa.String(length=36), nullable=False),
            sa.Column("event_id", sa.String(length=36), nullable=False),
            sa.Column("weight_contribution", sa.Float(), nullable=False),
            sa.Column("contribution_timestamp", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("aggregation_lineage", schema=None) as batch_op:
            batch_op.create_index("ix_lineage_event", ["event_id"], unique=False)
            batch_op.create_index(
                "ix_lineage_projection", ["projection_id"], unique=False
            )

    if "topic_model_versions" not in tables:
        op.create_table(
            "topic_model_versions",
            sa.Column("version_id", sa.String(length=50), nullable=False),
            sa.Column("trained_at", sa.DateTime(), nullable=False),
            sa.Column("hyperparameters", sa.JSON(), nullable=False),
            sa.Column("corpus_checksum", sa.String(length=64), nullable=False),
            sa.PrimaryKeyConstraint("version_id"),
        )

    if "topic_mappings" not in tables:
        op.create_table(
            "topic_mappings",
            sa.Column("version_from", sa.String(length=50), nullable=False),
            sa.Column("topic_from", sa.String(length=200), nullable=False),
            sa.Column("version_to", sa.String(length=50), nullable=False),
            sa.Column("topic_to", sa.String(length=200), nullable=False),
            sa.Column("wasserstein_distance", sa.Float(), nullable=False),
            sa.Column("mapping_confidence", sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint(
                "version_from", "topic_from", "version_to", "topic_to"
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("topic_matrix", schema=None) as batch_op:
        batch_op.drop_column("dominant_frame")
        batch_op.drop_column("dominant_emotion")
        batch_op.drop_column("demand_count")
        batch_op.drop_column("risk_score")
        batch_op.drop_column("avg_sentiment")
        batch_op.drop_column("mention_count")

    with op.batch_alter_table("topic_matrices", schema=None) as batch_op:
        batch_op.drop_column("topic_details")

    op.drop_table("topic_mappings")
    op.drop_table("topic_model_versions")
    op.drop_table("aggregation_lineage")
    op.drop_table("actor_topic_documents")
    op.drop_table("actor_topic_projection")
    op.drop_table("segment_events")
