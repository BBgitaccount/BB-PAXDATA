import sqlite3


def check_counts(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]

    print(f"=== Database Table Row Counts ({db_name}) ===")
    for table in sorted(tables):
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            print(f"{table:30} : {count}")
        except Exception as e:
            print(f"{table:30} : Error: {e}")

    conn.close()


if __name__ == "__main__":
    check_counts("bb-paxdata-temp.db")
