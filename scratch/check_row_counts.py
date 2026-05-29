import sqlite3


def check_counts():
    conn = sqlite3.connect("bb-paxdata.db")
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]

    print("=== Database Table Row Counts ===")
    for table in sorted(tables):
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            print(f"{table:30} : {count}")
        except Exception as e:
            print(f"{table:30} : Error: {e}")

    conn.close()


if __name__ == "__main__":
    check_counts()
