"""perf_1_gat_embedding_binary_storage

PERF-1: Change GAT embedding storage from JSON to binary numpy array for performance.

Revision ID: perf_1_gat_binary
Revises: 20260606_gat
Create Date: 2026-06-07 12:00:00.000000

"""

from __future__ import annotations

import json

import numpy as np
import sqlalchemy as sa

from alembic import op

revision: str = "perf_1_gat_binary"
down_revision: str | None = "20260606_gat"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "gat_embeddings" not in tables:
        return

    # Check if embedding_json column exists (old schema)
    columns = [col["name"] for col in inspector.get_columns("gat_embeddings")]

    if "embedding_json" in columns and "embedding_bytes" not in columns:
        # Step 1: Add new column
        op.add_column(
            "gat_embeddings",
            sa.Column(
                "embedding_bytes",
                sa.LargeBinary,
                nullable=True,
                comment="256-dim GAT embedding as binary numpy array",
            ),
        )

        # Step 2: Migrate data from JSON to binary
        # Read existing data, convert JSON to numpy array, then to bytes
        result = conn.execute(
            sa.text("SELECT actor_id, session_id, embedding_json FROM gat_embeddings")
        )

        for row in result:
            actor_id, session_id, embedding_json = row
            try:
                # Parse JSON to list, convert to numpy array, then to bytes
                embedding_list = json.loads(embedding_json)
                embedding_array = np.array(embedding_list, dtype=np.float32)
                embedding_bytes = embedding_array.tobytes()

                conn.execute(
                    sa.text(
                        "UPDATE gat_embeddings SET embedding_bytes = :bytes "
                        "WHERE actor_id = :actor_id AND session_id = :session_id"
                    ),
                    {
                        "bytes": embedding_bytes,
                        "actor_id": actor_id,
                        "session_id": session_id,
                    },
                )
            except Exception as e:
                # Log error but continue with other records
                print(f"Error migrating embedding for {actor_id}/{session_id}: {e}")

        # Step 3: Make new column NOT NULL
        # SQLite doesn't support ALTER COLUMN directly, use batch_alter_table
        with op.batch_alter_table("gat_embeddings", schema=None) as batch_op:
            batch_op.alter_column(
                "embedding_bytes",
                nullable=False,
            )

        # Step 4: Drop old column
        op.drop_column("gat_embeddings", "embedding_json")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "gat_embeddings" not in tables:
        return

    columns = [col["name"] for col in inspector.get_columns("gat_embeddings")]

    if "embedding_bytes" in columns and "embedding_json" not in columns:
        # Step 1: Add old column
        op.add_column(
            "gat_embeddings",
            sa.Column(
                "embedding_json",
                sa.Text,
                nullable=True,
                comment="256-dim GAT embedding as JSON float array",
            ),
        )

        # Step 2: Migrate data from binary to JSON
        result = conn.execute(
            sa.text("SELECT actor_id, session_id, embedding_bytes FROM gat_embeddings")
        )

        for row in result:
            actor_id, session_id, embedding_bytes = row
            try:
                # Convert bytes to numpy array, then to list, then to JSON
                embedding_array = np.frombuffer(embedding_bytes, dtype=np.float32)
                embedding_list = embedding_array.tolist()
                embedding_json = json.dumps(embedding_list)

                conn.execute(
                    sa.text(
                        "UPDATE gat_embeddings SET embedding_json = :json "
                        "WHERE actor_id = :actor_id AND session_id = :session_id"
                    ),
                    {
                        "json": embedding_json,
                        "actor_id": actor_id,
                        "session_id": session_id,
                    },
                )
            except Exception as e:
                # Log error but continue with other records
                print(f"Error migrating embedding for {actor_id}/{session_id}: {e}")

        # Step 3: Make old column NOT NULL
        # SQLite doesn't support ALTER COLUMN directly, use batch_alter_table
        with op.batch_alter_table("gat_embeddings", schema=None) as batch_op:
            batch_op.alter_column(
                "embedding_json",
                nullable=False,
            )

        # Step 4: Drop new column
        op.drop_column("gat_embeddings", "embedding_bytes")
