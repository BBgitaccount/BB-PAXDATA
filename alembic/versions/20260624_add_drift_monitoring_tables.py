"""Add drift monitoring tables

Revision ID: 20260624_add_drift_monitoring_tables
Revises: 
Create Date: 2024-06-24

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260624_add_drift_mon_tabs"
down_revision = None  # Set to the latest migration ID
branch_labels = None
depends_on = None


def upgrade():
    # Create drift_measurements table
    op.execute(
        """
    CREATE TABLE drift_measurements (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        metric      VARCHAR(20)  NOT NULL,
        field       VARCHAR(50)  NOT NULL,
        value       FLOAT        NOT NULL,
        severity    VARCHAR(10)  NOT NULL,
        baseline_start TIMESTAMPTZ,
        baseline_end   TIMESTAMPTZ,
        current_start  TIMESTAMPTZ,
        current_end    TIMESTAMPTZ,
        metadata    JSONB        DEFAULT '{}',
        created_at  TIMESTAMPTZ  DEFAULT NOW()
    );
    """
    )

    op.execute(
        "CREATE INDEX idx_drift_field_created ON drift_measurements(field, created_at);"
    )

    # Create drift_alerts table
    op.execute(
        """
    CREATE TABLE drift_alerts (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        alert_type      VARCHAR(20)  NOT NULL,
        field           VARCHAR(50)  NOT NULL,
        severity        VARCHAR(10)  NOT NULL,
        detected_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        resolved        BOOLEAN      NOT NULL DEFAULT FALSE,
        resolved_at     TIMESTAMPTZ,
        metadata        JSONB        DEFAULT '{}',
        retraining_triggered BOOLEAN NOT NULL DEFAULT FALSE
    );
    """
    )

    op.execute(
        "CREATE INDEX idx_drift_alerts_field_resolved ON drift_alerts(field, resolved);"
    )
    op.execute("CREATE INDEX idx_drift_alerts_created ON drift_alerts(detected_at);")

    # Create drift_reports table
    op.execute(
        """
    CREATE TABLE drift_reports (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        report_period   VARCHAR(20)  NOT NULL UNIQUE,
        generated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        summary         JSONB        NOT NULL,
        field_details   JSONB        NOT NULL
    );
    """
    )

    op.execute("CREATE INDEX idx_drift_reports_period ON drift_reports(report_period);")


def downgrade():
    op.drop_index("idx_drift_reports_period", table_name="drift_reports")
    op.drop_table("drift_reports")

    op.drop_index("idx_drift_alerts_created", table_name="drift_alerts")
    op.drop_index("idx_drift_alerts_field_resolved", table_name="drift_alerts")
    op.drop_table("drift_alerts")

    op.drop_index("idx_drift_field_created", table_name="drift_measurements")
    op.drop_table("drift_measurements")
