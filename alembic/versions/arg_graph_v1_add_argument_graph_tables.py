"""add argument graph tables

Revision ID: arg_graph_v1
Revises: f3636f730190
Create Date: 2026-06-04 23:30:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "arg_graph_v1"
down_revision = "f3636f730190"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create nodes table
    op.create_table(
        "argument_graph_nodes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("graph_id", sa.Text(), nullable=False),
        sa.Column("segment_id", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("node_type", sa.Text(), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True, default=1.0),
        sa.Column("stance", sa.Text(), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=True, default=0),
        sa.Column("predicate", sa.Text(), nullable=True),
        sa.Column("is_negated", sa.Boolean(), nullable=True, default=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_arg_node_graph", "argument_graph_nodes", ["graph_id"])
    op.create_index("idx_arg_node_speaker", "argument_graph_nodes", ["speaker"])
    op.create_index("idx_arg_node_type", "argument_graph_nodes", ["node_type"])

    # Create edges table
    op.create_table(
        "argument_graph_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("graph_id", sa.Text(), nullable=False),
        sa.Column("edge_id", sa.Text(), nullable=False, unique=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True, default=1.0),
        sa.Column("weight", sa.Float(), nullable=True, default=1.0),
        sa.Column("is_cross_speaker", sa.Boolean(), nullable=True, default=False),
        sa.Column("evidence_snippet", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_edge_graph", "argument_graph_edges", ["graph_id"])
    op.create_index(
        "idx_edge_source_target", "argument_graph_edges", ["source_id", "target_id"]
    )
    op.create_index("idx_edge_type", "argument_graph_edges", ["relation_type"])

    # Create metadata table
    op.create_table(
        "argument_graphs_metadata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("graph_id", sa.Text(), unique=True, nullable=False),
        sa.Column("document_id", sa.Text(), nullable=True),
        sa.Column("root_claim_ids", sa.JSON(), nullable=True),
        sa.Column("total_nodes", sa.Integer(), nullable=True, default=0),
        sa.Column("total_edges", sa.Integer(), nullable=True, default=0),
        sa.Column("max_depth", sa.Integer(), nullable=True, default=0),
        sa.Column("graph_density", sa.Float(), nullable=True, default=0.0),
        sa.Column("claim_count", sa.Integer(), nullable=True, default=0),
        sa.Column("attack_count", sa.Integer(), nullable=True, default=0),
        sa.Column("support_count", sa.Integer(), nullable=True, default=0),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("processing_time_ms", sa.Float(), nullable=True, default=0.0),
        sa.Column("graph_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_arg_meta_doc", "argument_graphs_metadata", ["document_id"])


def downgrade() -> None:
    op.drop_table("argument_graphs_metadata")
    op.drop_table("argument_graph_edges")
    op.drop_table("argument_graph_nodes")
