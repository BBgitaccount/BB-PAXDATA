import sqlite3
from pathlib import Path


def inspect_db():
    db_path = Path("bb-paxdata.db")
    if not db_path.exists():
        print("Database does not exist.")
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables and Row Counts:")
    for table in sorted(tables):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count}")
    conn.close()


if __name__ == "__main__":
    inspect_db()
