"""fix_country_stats_composite_pk

Fixes the country_stats table to use (country, file_id) as a composite
primary key instead of just (country).  This matches the ORM model definition
and allows the same country code to appear in multiple files.

Revision ID: fix_cs_composite_pk
Revises: 9042307bdc61
Create Date: 2026-05-29
"""

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON

from alembic import op

# revision identifiers, used by Alembic.
revision = "fix_cs_composite_pk"
down_revision = "9042307bdc61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER TABLE to change primary keys,
    # so we drop and recreate the table with the correct composite PK.
    op.rename_table("country_stats", "country_stats_old")

    op.create_table(
        "country_stats",
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column(
            "file_id", sa.String(), sa.ForeignKey("files.file_id"), nullable=False
        ),
        sa.Column("n_segments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_sentences", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_words", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_duration_sec", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("words_per_minute", sa.Float(), nullable=True),
        sa.Column("avg_sentiment", sa.Float(), nullable=True),
        sa.Column("dominant_emotion", sa.Text(), nullable=True),
        sa.Column("dominant_topic", sa.Text(), nullable=True),
        sa.Column("topic_scores", JSON(), nullable=True),
        sa.PrimaryKeyConstraint("country", "file_id"),
    )

    # Copy data from old table (if any exists)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "INSERT INTO country_stats "
            "(country, file_id, n_segments, n_sentences, total_words, "
            "total_duration_sec, words_per_minute, avg_sentiment, "
            "dominant_emotion, dominant_topic, topic_scores) "
            "SELECT country, file_id, n_segments, n_sentences, total_words, "
            "total_duration_sec, words_per_minute, avg_sentiment, "
            "dominant_emotion, dominant_topic, topic_scores "
            "FROM country_stats_old "
            "ON CONFLICT (country, file_id) DO NOTHING"
        )
    else:
        op.execute(
            "INSERT OR IGNORE INTO country_stats "
            "(country, file_id, n_segments, n_sentences, total_words, "
            "total_duration_sec, words_per_minute, avg_sentiment, "
            "dominant_emotion, dominant_topic, topic_scores) "
            "SELECT country, file_id, n_segments, n_sentences, total_words, "
            "total_duration_sec, words_per_minute, avg_sentiment, "
            "dominant_emotion, dominant_topic, topic_scores "
            "FROM country_stats_old"
        )

    op.drop_table("country_stats_old")


def downgrade() -> None:
    # Revert to single-column PK (lossy — duplicates will be dropped)
    op.rename_table("country_stats", "country_stats_new")

    op.create_table(
        "country_stats",
        sa.Column("country", sa.Text(), nullable=False, primary_key=True),
        sa.Column(
            "file_id", sa.String(), sa.ForeignKey("files.file_id"), nullable=False
        ),
        sa.Column("n_segments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_sentences", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_words", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_duration_sec", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("words_per_minute", sa.Float(), nullable=True),
        sa.Column("avg_sentiment", sa.Float(), nullable=True),
        sa.Column("dominant_emotion", sa.Text(), nullable=True),
        sa.Column("dominant_topic", sa.Text(), nullable=True),
        sa.Column("topic_scores", JSON(), nullable=True),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "INSERT INTO country_stats "
            "(country, file_id, n_segments, n_sentences, total_words, "
            "total_duration_sec, words_per_minute, avg_sentiment, "
            "dominant_emotion, dominant_topic, topic_scores) "
            "SELECT country, file_id, n_segments, n_sentences, total_words, "
            "total_duration_sec, words_per_minute, avg_sentiment, "
            "dominant_emotion, dominant_topic, topic_scores "
            "FROM country_stats_new "
            "ON CONFLICT (country) DO NOTHING"
        )
    else:
        op.execute(
            "INSERT OR IGNORE INTO country_stats "
            "(country, file_id, n_segments, n_sentences, total_words, "
            "total_duration_sec, words_per_minute, avg_sentiment, "
            "dominant_emotion, dominant_topic, topic_scores) "
            "SELECT country, file_id, n_segments, n_sentences, total_words, "
            "total_duration_sec, words_per_minute, avg_sentiment, "
            "dominant_emotion, dominant_topic, topic_scores "
            "FROM country_stats_new"
        )

    op.drop_table("country_stats_new")
