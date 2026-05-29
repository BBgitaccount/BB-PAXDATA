import sqlite3

conn = sqlite3.connect("bb-paxdata.db")
r = conn.execute(
    "SELECT sql FROM sqlite_master WHERE name='pattern_records'"
).fetchone()
print(r[0] if r else "None")
conn.close()
