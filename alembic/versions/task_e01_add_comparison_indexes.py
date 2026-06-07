"""task_e01_add_comparison_indexes

Revision ID: task_e01_add_comparison_indexes
Revises: c9e693fb9bfb
Create Date: 2025-01-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "task_e01_add_comparison_indexes"
down_revision: Union[str, None] = "c9e693fb9bfb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect, text

    inspector = inspect(bind)

    # Helper function to check if index exists
    def index_exists(table_name, index_name):
        indexes = inspector.get_indexes(table_name)
        return any(idx["name"] == index_name for idx in indexes)

    # Speaker positions indexes
    if not index_exists("speaker_positions", "ix_speaker_positions_session_id"):
        op.execute(
            text(
                "CREATE INDEX ix_speaker_positions_session_id ON speaker_positions(session_id)"
            )
        )

    if not index_exists("speaker_positions", "ix_speaker_positions_speaker_id"):
        op.execute(
            text(
                "CREATE INDEX ix_speaker_positions_speaker_id ON speaker_positions(speaker_id)"
            )
        )

    # DKI results indexes
    if not index_exists("dki_results", "ix_dki_results_session_id"):
        op.execute(
            text("CREATE INDEX ix_dki_results_session_id ON dki_results(session_id)")
        )

    if not index_exists("dki_results", "ix_dki_results_speaker_id"):
        op.execute(
            text("CREATE INDEX ix_dki_results_speaker_id ON dki_results(speaker_id)")
        )

    # AI sentence analysis indexes
    if not index_exists("ai_sentence_analysis", "ix_ai_sentence_analysis_session_id"):
        op.execute(
            text(
                "CREATE INDEX ix_ai_sentence_analysis_session_id ON ai_sentence_analysis(session_id)"
            )
        )

    if not index_exists("ai_sentence_analysis", "ix_ai_sentence_analysis_speaker_name"):
        op.execute(
            text(
                "CREATE INDEX ix_ai_sentence_analysis_speaker_name ON ai_sentence_analysis(speaker_name)"
            )
        )

    # Discourse flows indexes
    if not index_exists("discourse_flows", "ix_discourse_flows_file_id"):
        op.execute(
            text("CREATE INDEX ix_discourse_flows_file_id ON discourse_flows(file_id)")
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect, text

    inspector = inspect(bind)

    # Helper function to check if index exists
    def index_exists(table_name, index_name):
        indexes = inspector.get_indexes(table_name)
        return any(idx["name"] == index_name for idx in indexes)

    # Drop indexes in reverse order
    if index_exists("discourse_flows", "ix_discourse_flows_file_id"):
        op.execute(text("DROP INDEX ix_discourse_flows_file_id"))

    if index_exists("ai_sentence_analysis", "ix_ai_sentence_analysis_speaker_name"):
        op.execute(text("DROP INDEX ix_ai_sentence_analysis_speaker_name"))

    if index_exists("ai_sentence_analysis", "ix_ai_sentence_analysis_session_id"):
        op.execute(text("DROP INDEX ix_ai_sentence_analysis_session_id"))

    if index_exists("dki_results", "ix_dki_results_speaker_id"):
        op.execute(text("DROP INDEX ix_dki_results_speaker_id"))

    if index_exists("dki_results", "ix_dki_results_session_id"):
        op.execute(text("DROP INDEX ix_dki_results_session_id"))

    if index_exists("speaker_positions", "ix_speaker_positions_speaker_id"):
        op.execute(text("DROP INDEX ix_speaker_positions_speaker_id"))

    if index_exists("speaker_positions", "ix_speaker_positions_session_id"):
        op.execute(text("DROP INDEX ix_speaker_positions_session_id"))
