"""Add retraining and shadow deployment tables

Revision ID: 20260624_add_retraining_and_shadow_tables
Revises: 20260624_add_drift_monitoring_tables
Create Date: 2024-06-24

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260624_add_retraining_and_shadow_tables"
down_revision = "20260624_add_drift_monitoring_tables"
branch_labels = None
depends_on = None


def upgrade():
    # Create retraining_jobs table
    op.execute(
        """
    CREATE TABLE retraining_jobs (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        trigger_reason  VARCHAR(20)  NOT NULL,
        fields          TEXT[]       NOT NULL,
        status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
        created_at      TIMESTAMPTZ  DEFAULT NOW(),
        completed_at    TIMESTAMPTZ,
        metadata        JSONB        DEFAULT '{}'
    );
    """
    )

    op.execute("CREATE INDEX idx_retraining_jobs_status ON retraining_jobs(status);")
    op.execute(
        "CREATE INDEX idx_retraining_jobs_created ON retraining_jobs(created_at);"
    )

    # Create model_versions table
    op.execute(
        """
    CREATE TABLE model_versions (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        model_type      VARCHAR(30)  NOT NULL,
        version_tag     VARCHAR(20)  NOT NULL,
        artifacts_path  TEXT         NOT NULL,
        status          VARCHAR(15)  NOT NULL DEFAULT 'shadow',
        deployed_at     TIMESTAMPTZ  DEFAULT NOW(),
        metrics         JSONB        DEFAULT '{}'
    );
    """
    )

    op.execute(
        "CREATE INDEX idx_model_versions_type_status ON model_versions(model_type, status);"
    )
    op.execute("CREATE INDEX idx_model_versions_tag ON model_versions(version_tag);")

    # Create shadow_results table
    op.execute(
        """
    CREATE TABLE shadow_results (
        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        analysis_id           UUID,
        production_version_id  UUID,
        shadow_version_id      UUID,
        production_output     JSONB,
        shadow_output          JSONB,
        agreement             BOOLEAN,
        delta                 FLOAT,
        created_at            TIMESTAMPTZ DEFAULT NOW()
    );
    """
    )

    op.execute(
        "CREATE INDEX idx_shadow_results_analysis ON shadow_results(analysis_id);"
    )
    op.execute(
        "CREATE INDEX idx_shadow_results_shadow_version ON shadow_results(shadow_version_id);"
    )

    # Create training_datasets table
    op.execute(
        """
    CREATE TABLE training_datasets (
        dataset_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        split           VARCHAR(20)  NOT NULL,
        field           VARCHAR(50)  NOT NULL,
        sample_ids      UUID[]       NOT NULL,
        created_at      TIMESTAMPTZ  DEFAULT NOW()
    );
    """
    )

    op.execute(
        "CREATE INDEX idx_training_datasets_split_field ON training_datasets(split, field);"
    )


def downgrade():
    op.drop_index("idx_training_datasets_split_field", table_name="training_datasets")
    op.drop_table("training_datasets")

    op.drop_index("idx_shadow_results_shadow_version", table_name="shadow_results")
    op.drop_index("idx_shadow_results_analysis", table_name="shadow_results")
    op.drop_table("shadow_results")

    op.drop_index("idx_model_versions_tag", table_name="model_versions")
    op.drop_index("idx_model_versions_type_status", table_name="model_versions")
    op.drop_table("model_versions")

    op.drop_index("idx_retraining_jobs_created", table_name="retraining_jobs")
    op.drop_index("idx_retraining_jobs_status", table_name="retraining_jobs")
    op.drop_table("retraining_jobs")
