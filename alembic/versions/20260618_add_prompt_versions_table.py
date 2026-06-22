"""Add prompt_versions table for database-backed prompt version management

Revision ID: 20260618_apvt
Revises: 20260614_rlmt
Create Date: 2026-06-18 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260618_apvt"
down_revision = "20260614_rlmt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "model_name", sa.String(length=100), nullable=False, server_default="gpt-4o"
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "language", sa.String(length=10), nullable=False, server_default="any"
        ),
        sa.Column("academic_ref", sa.Text(), nullable=True),
        sa.Column("template_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_id", "version", name="uq_prompt_id_version"),
    )
    op.create_index("idx_prompt_versions_prompt_id", "prompt_versions", ["prompt_id"])
    op.create_index(
        "idx_prompt_versions_template_hash", "prompt_versions", ["template_hash"]
    )
    op.create_index(
        "idx_prompt_id_active", "prompt_versions", ["prompt_id", "is_active"]
    )
    op.create_index(
        "idx_prompt_id_language", "prompt_versions", ["prompt_id", "language"]
    )


def downgrade() -> None:
    op.drop_index("idx_prompt_id_language", table_name="prompt_versions")
    op.drop_index("idx_prompt_id_active", table_name="prompt_versions")
    op.drop_index("idx_prompt_versions_template_hash", table_name="prompt_versions")
    op.drop_index("idx_prompt_versions_prompt_id", table_name="prompt_versions")
    op.drop_table("prompt_versions")
