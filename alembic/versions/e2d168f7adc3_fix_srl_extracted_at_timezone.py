"""fix_srl_extracted_at_timezone

Revision ID: e2d168f7adc3
Revises: 16f1baf5e5e2
Create Date: 2026-06-10 23:27:53.832883

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2d168f7adc3"
down_revision: str | None = "16f1baf5e5e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    try:
        with op.batch_alter_table("ai_sentence_analysis", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_ai_sentence_analysis_speaker_name"))
    except Exception:
        pass

    with op.batch_alter_table("argument_graph_edges", schema=None) as batch_op:
        batch_op.alter_column(
            "confidence",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            nullable=False,
        )
        batch_op.alter_column(
            "weight", existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=False
        )
        batch_op.alter_column(
            "is_cross_speaker", existing_type=sa.BOOLEAN(), nullable=False
        )
        batch_op.alter_column(
            "created_at", existing_type=postgresql.TIMESTAMP(), nullable=False
        )
        batch_op.create_index(
            batch_op.f("ix_argument_graph_edges_graph_id"), ["graph_id"], unique=False
        )

    with op.batch_alter_table("argument_graph_nodes", schema=None) as batch_op:
        batch_op.alter_column(
            "confidence",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            nullable=False,
        )
        batch_op.alter_column("depth", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column("is_negated", existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.alter_column(
            "created_at", existing_type=postgresql.TIMESTAMP(), nullable=False
        )
        batch_op.create_index(
            batch_op.f("ix_argument_graph_nodes_graph_id"), ["graph_id"], unique=False
        )

    with op.batch_alter_table("argument_graphs_metadata", schema=None) as batch_op:
        batch_op.alter_column("total_nodes", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column("total_edges", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column("max_depth", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column(
            "graph_density",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            nullable=False,
        )
        batch_op.alter_column("claim_count", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column(
            "attack_count", existing_type=sa.INTEGER(), nullable=False
        )
        batch_op.alter_column(
            "support_count", existing_type=sa.INTEGER(), nullable=False
        )
        batch_op.alter_column(
            "processing_time_ms",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            nullable=False,
        )
        batch_op.alter_column(
            "created_at", existing_type=postgresql.TIMESTAMP(), nullable=False
        )
        batch_op.alter_column(
            "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=False
        )

    with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
        batch_op.alter_column(
            "power_level_a",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=None,
            existing_nullable=False,
        )
        batch_op.alter_column(
            "power_level_b",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=None,
            existing_nullable=False,
        )
        batch_op.alter_column(
            "demand_weight",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=None,
            existing_nullable=False,
        )
        batch_op.alter_column(
            "risk_severity",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=None,
            existing_nullable=False,
        )

    with op.batch_alter_table("discourse_flows", schema=None) as batch_op:
        batch_op.alter_column(
            "narrative_salience",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=None,
            existing_nullable=False,
        )
        batch_op.drop_index(batch_op.f("ix_discourse_flows_file_id"))

    with op.batch_alter_table(
        "discourse_network_edges_legacy", schema=None
    ) as batch_op:
        batch_op.alter_column(
            "predicate",
            existing_type=sa.TEXT(),
            comment='Extracted predicate/verb from SRL frame (e.g., "reject", "support")',
            existing_nullable=True,
        )
        batch_op.alter_column(
            "arg1_entity",
            existing_type=sa.TEXT(),
            comment="ARG1/Patient entity text (target of action)",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "arg0_entity",
            existing_type=sa.TEXT(),
            comment="ARG0/Agent entity text (actor performing action)",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "srl_frame_json",
            existing_type=sa.TEXT(),
            comment="Complete SRL frame as JSON for advanced queries",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "srl_confidence",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            comment="SRL extraction confidence score (0-1)",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "is_negated",
            existing_type=sa.BOOLEAN(),
            server_default=None,
            comment="True if action was negated in source text",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "srl_extracted_at",
            existing_type=postgresql.TIMESTAMP(),
            server_default=None,
            type_=sa.DateTime(timezone=True),
            comment="Timestamp when SRL enrichment was applied",
            existing_nullable=True,
        )
        batch_op.create_table_comment(
            "Bilateral discourse relationships enriched with SRL semantics",
            existing_comment=None,
        )

    with op.batch_alter_table("domain_events", schema=None) as batch_op:
        batch_op.alter_column(
            "event_version",
            existing_type=sa.INTEGER(),
            server_default=None,
            existing_nullable=False,
        )
        batch_op.create_index(
            batch_op.f("ix_domain_events_aggregate_id"), ["aggregate_id"], unique=False
        )

    with op.batch_alter_table("gat_embeddings", schema=None) as batch_op:
        batch_op.alter_column(
            "anomaly_score",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=None,
            comment="Anomaly score or -1 sentinel",
            existing_comment="Anomaly score [0,1] or -1 sentinel",
            existing_nullable=False,
        )

    with op.batch_alter_table("sentences", schema=None) as batch_op:
        batch_op.alter_column(
            "formula_inconsistency_score",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=None,
            existing_nullable=False,
        )
        batch_op.alter_column(
            "discrepancy_score",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=None,
            existing_nullable=False,
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("sentences", schema=None) as batch_op:
        batch_op.alter_column(
            "discrepancy_score",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("0.0"),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "formula_inconsistency_score",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("0.0"),
            existing_nullable=False,
        )

    with op.batch_alter_table("gat_embeddings", schema=None) as batch_op:
        batch_op.alter_column(
            "anomaly_score",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("'-1'::double precision"),
            comment="Anomaly score [0,1] or -1 sentinel",
            existing_comment="Anomaly score or -1 sentinel",
            existing_nullable=False,
        )

    with op.batch_alter_table("domain_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_domain_events_aggregate_id"))
        batch_op.alter_column(
            "event_version",
            existing_type=sa.INTEGER(),
            server_default=sa.text("1"),
            existing_nullable=False,
        )

    with op.batch_alter_table(
        "discourse_network_edges_legacy", schema=None
    ) as batch_op:
        batch_op.drop_table_comment(
            existing_comment="Bilateral discourse relationships enriched with SRL semantics"
        )
        batch_op.alter_column(
            "srl_extracted_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            type_=postgresql.TIMESTAMP(),
            comment=None,
            existing_comment="Timestamp when SRL enrichment was applied",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "is_negated",
            existing_type=sa.BOOLEAN(),
            server_default=sa.text("false"),
            comment=None,
            existing_comment="True if action was negated in source text",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "srl_confidence",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            comment=None,
            existing_comment="SRL extraction confidence score (0-1)",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "srl_frame_json",
            existing_type=sa.TEXT(),
            comment=None,
            existing_comment="Complete SRL frame as JSON for advanced queries",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "arg0_entity",
            existing_type=sa.TEXT(),
            comment=None,
            existing_comment="ARG0/Agent entity text (actor performing action)",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "arg1_entity",
            existing_type=sa.TEXT(),
            comment=None,
            existing_comment="ARG1/Patient entity text (target of action)",
            existing_nullable=True,
        )
        batch_op.alter_column(
            "predicate",
            existing_type=sa.TEXT(),
            comment=None,
            existing_comment='Extracted predicate/verb from SRL frame (e.g., "reject", "support")',
            existing_nullable=True,
        )

    with op.batch_alter_table("discourse_flows", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_discourse_flows_file_id"), ["file_id"], unique=False
        )
        batch_op.alter_column(
            "narrative_salience",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("0.0"),
            existing_nullable=False,
        )

    with op.batch_alter_table("bilateral_sentiments", schema=None) as batch_op:
        batch_op.alter_column(
            "risk_severity",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("1.0"),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "demand_weight",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("1.0"),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "power_level_b",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("1.0"),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "power_level_a",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("1.0"),
            existing_nullable=False,
        )

    with op.batch_alter_table("argument_graphs_metadata", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=True
        )
        batch_op.alter_column(
            "created_at", existing_type=postgresql.TIMESTAMP(), nullable=True
        )
        batch_op.alter_column(
            "processing_time_ms",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            nullable=True,
        )
        batch_op.alter_column(
            "support_count", existing_type=sa.INTEGER(), nullable=True
        )
        batch_op.alter_column("attack_count", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column("claim_count", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column(
            "graph_density",
            existing_type=sa.DOUBLE_PRECISION(precision=53),
            nullable=True,
        )
        batch_op.alter_column("max_depth", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column("total_edges", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column("total_nodes", existing_type=sa.INTEGER(), nullable=True)

    with op.batch_alter_table("argument_graph_nodes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_argument_graph_nodes_graph_id"))
        batch_op.alter_column(
            "created_at", existing_type=postgresql.TIMESTAMP(), nullable=True
        )
        batch_op.alter_column("is_negated", existing_type=sa.BOOLEAN(), nullable=True)
        batch_op.alter_column("depth", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column(
            "confidence", existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=True
        )

    with op.batch_alter_table("argument_graph_edges", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_argument_graph_edges_graph_id"))
        batch_op.alter_column(
            "created_at", existing_type=postgresql.TIMESTAMP(), nullable=True
        )
        batch_op.alter_column(
            "is_cross_speaker", existing_type=sa.BOOLEAN(), nullable=True
        )
        batch_op.alter_column(
            "weight", existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=True
        )
        batch_op.alter_column(
            "confidence", existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=True
        )

    with op.batch_alter_table("ai_sentence_analysis", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ai_sentence_analysis_speaker_name"),
            ["speaker_name"],
            unique=False,
        )

    # ### end Alembic commands ###
