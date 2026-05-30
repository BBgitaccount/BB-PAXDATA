# scratch/check_db.py
import json
import sqlite3

db_path = "bb-paxdata.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()


def print_table_sample(table_name, limit=2):
    print(f"\n--- Table: {table_name} ---")
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"Total Rows: {count}")

        if count > 0:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]

            cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
            rows = cursor.fetchall()

            for row in rows:
                row_dict = dict(zip(columns, row))
                print(json.dumps(row_dict, indent=2, default=str))
    except Exception as e:
        print(f"Error querying {table_name}: {e}")


# Inspect all 6 new tables
tables = [
    "segment_events",
    "actor_topic_projection",
    "actor_topic_documents",
    "aggregation_lineage",
    "topic_model_versions",
    "topic_mappings",
]

for table in tables:
    print_table_sample(table)

# Check topic_matrix legacy table to make sure it's populated too
print_table_sample("topic_matrix")

conn.close()
