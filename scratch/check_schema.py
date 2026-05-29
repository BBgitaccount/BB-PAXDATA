import sqlite3

conn = sqlite3.connect("bb-paxdata.db")
c = conn.cursor()
for table in ["topic_matrix"]:
    c.execute(f"SELECT sql FROM sqlite_master WHERE name='{table}'")
    row = c.fetchone()
    print(f"{table} schema:")
    print(row[0] if row else "TABLE NOT FOUND")
    print("-" * 50)
conn.close()
