import sqlite3

conn = sqlite3.connect("bb-paxdata.db")
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE name='country_stats'")
row = c.fetchone()
print("country_stats schema:")
print(row[0] if row else "TABLE NOT FOUND")
conn.close()
