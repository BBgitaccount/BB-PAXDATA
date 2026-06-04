import os
import sqlite3

db_path = "paxdata.db"

if not os.path.exists(db_path):
    print(f"Database {db_path} does not exist in current directory.")
else:
    print(f"Applying indexes to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # ai_sentence_analysis indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_prompt_processed ON ai_sentence_analysis (prompt_version, processed_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_processed_at ON ai_sentence_analysis (processed_at)"
        )

        # human_reviews indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_review_status_created ON human_reviews (agreement_status, created_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_review_created_at ON human_reviews (created_at)"
        )

        conn.commit()
        print("Indexes successfully applied.")
    except Exception as e:
        print(f"Error applying indexes: {e}")
    finally:
        conn.close()
