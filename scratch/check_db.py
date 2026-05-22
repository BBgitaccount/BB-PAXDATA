import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cursor = conn.cursor()

    cursor.execute("SELECT version_num FROM alembic_version")
    print(f"ALEMBIC VERSION: {cursor.fetchone()}")

    for table in [
        "human_reviews",
        "calibration_reports",
        "discourse_network_edges_legacy",
    ]:
        print(f"\nCOLUMNS FOR {table}:")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            for col in cursor.fetchall():
                print(f"  {col[1]} ({col[2]})")
        except Exception as e:
            print(f"  Error: {e}")

    conn.close()


if __name__ == "__main__":
    main()
