"""Verify row counts for all 14 potentially empty tables."""

import sys
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import text

from bb_paxdata.infrastructure.db.session import get_db_session

TABLES_TO_CHECK = [
    "webhook_subscriptions",
    "topic_model_versions",
    "topic_mappings",  # Correct table name (plural)
    "speaker_positions",
    "outbox_events",
    "gat_embeddings",
    "dki_results",
    "dead_letter_events",
    "calibration_reports",
    "audit_entries",
    "argument_graphs_metadata",
    "argument_graph_edges",
    "aggregation_lineage",
]


def main():
    """Check row counts for all tables."""
    print("Checking row counts for 14 potentially empty tables...\n")

    results = []
    for table in TABLES_TO_CHECK:
        # Use separate session for each query to avoid transaction abort cascading
        try:
            with get_db_session() as sess:
                count = sess.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                results.append((table, count))
                print(f"{table:30s} : {count:6d} rows")
        except Exception:
            results.append((table, "TABLE_MISSING"))
            print(f"{table:30s} : TABLE DOES NOT EXIST")

        # Sort by count (ascending)
        results.sort(key=lambda x: x[1] if isinstance(x[1], int) else 999999)

        print("\n" + "=" * 60)
        print("SUMMARY - Empty Tables (count = 0):")
        print("=" * 60)
        empty_count = 0
        for table, count in results:
            if isinstance(count, int) and count == 0:
                print(f"  - {table}")
                empty_count += 1

        print(f"\nTotal empty tables: {empty_count}/{len(TABLES_TO_CHECK)}")


if __name__ == "__main__":
    main()
