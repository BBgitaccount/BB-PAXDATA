import sqlite3

conn = sqlite3.connect("bb-paxdata.db.old")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]

for table in tables:
    if table == "alembic_version":
        continue
    try:
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"{table}: {count}")
    except Exception as e:
        print(f"Error querying {table}: {e}")

conn.close()
