from bb_paxdata.config.settings import get_settings
from sqlalchemy import create_engine, text

settings = get_settings()
db_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite").replace(
    "postgresql+asyncpg", "postgresql"
)

# Create sync engine for table creation
engine = create_engine(db_url)

# Create the table manually using SQL
with engine.begin() as conn:
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS formula_validation_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id VARCHAR NOT NULL,
            sentence_code VARCHAR(50),
            entity_type VARCHAR NOT NULL,
            entity_id VARCHAR NOT NULL,
            formula_name VARCHAR NOT NULL,
            expected_constraint TEXT NOT NULL,
            actual_value FLOAT NOT NULL,
            status VARCHAR NOT NULL,
            details JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            human_verdict VARCHAR,
            human_note TEXT,
            human_review_id VARCHAR,
            human_corrected_value FLOAT,
            human_reviewed_at DATETIME,
            human_reviewed_by VARCHAR,
            human_reviewer_role VARCHAR,
            log_version INTEGER DEFAULT 1,
            is_current BOOLEAN DEFAULT 1,
            reviewer_id VARCHAR,
            locked_at DATETIME,
            superseded_by INTEGER,
            auto_triage_reason VARCHAR,
            confidence_at_review VARCHAR
        )
    """
        )
    )

    # Create indexes
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_fval_run ON formula_validation_logs(run_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_fval_entity ON formula_validation_logs(entity_type, entity_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_fval_formula ON formula_validation_logs(formula_name)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_fval_status ON formula_validation_logs(status)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_fval_sentence_code ON formula_validation_logs(sentence_code)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_fval_is_current ON formula_validation_logs(is_current)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_fval_reviewer ON formula_validation_logs(reviewer_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_fval_human_verdict ON formula_validation_logs(human_verdict)"
        )
    )

print("formula_validation_logs table created successfully")
