"""add srl fields to discourse network edges

Revision ID: f3636f730190
Revises: f2626f5f3e19
Create Date: 2026-06-04 23:07:25.281863

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3636f730190"
down_revision: str | None = "f2626f5f3e19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # Add SRL columns
    op.add_column(
        "discourse_network_edges_legacy",
        sa.Column("predicate", sa.Text(), nullable=True),
    )
    op.add_column(
        "discourse_network_edges_legacy",
        sa.Column("arg0_entity", sa.Text(), nullable=True),
    )
    op.add_column(
        "discourse_network_edges_legacy",
        sa.Column("arg1_entity", sa.Text(), nullable=True),
    )
    op.add_column(
        "discourse_network_edges_legacy",
        sa.Column("srl_frame_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "discourse_network_edges_legacy",
        sa.Column("srl_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "discourse_network_edges_legacy",
        sa.Column(
            "is_negated",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("0") if is_sqlite else sa.text("false"),
        ),
    )
    op.add_column(
        "discourse_network_edges_legacy",
        sa.Column(
            "srl_extracted_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    # Create Indexes
    op.create_index("idx_net_to", "discourse_network_edges_legacy", ["to_country"])
    op.create_index(
        "idx_net_predicate", "discourse_network_edges_legacy", ["predicate"]
    )
    op.create_index(
        "idx_net_bilateral",
        "discourse_network_edges_legacy",
        ["from_country", "to_country"],
    )

    # Create Check Constraint (Postgres only)
    if not is_sqlite:
        op.create_check_constraint(
            "ck_weight_non_negative", "discourse_network_edges_legacy", "weight >= 0"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if not is_sqlite:
        op.drop_constraint(
            "ck_weight_non_negative", "discourse_network_edges_legacy", type_="check"
        )

    op.drop_index("idx_net_bilateral", table_name="discourse_network_edges_legacy")
    op.drop_index("idx_net_predicate", table_name="discourse_network_edges_legacy")
    op.drop_index("idx_net_to", table_name="discourse_network_edges_legacy")

    op.drop_column("discourse_network_edges_legacy", "srl_extracted_at")
    op.drop_column("discourse_network_edges_legacy", "is_negated")
    op.drop_column("discourse_network_edges_legacy", "srl_confidence")
    op.drop_column("discourse_network_edges_legacy", "srl_frame_json")
    op.drop_column("discourse_network_edges_legacy", "arg1_entity")
    op.drop_column("discourse_network_edges_legacy", "arg0_entity")
    op.drop_column("discourse_network_edges_legacy", "predicate")
