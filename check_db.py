import sqlite3

conn = sqlite3.connect("bb-paxdata.db")
cursor = conn.cursor()

# Check tables
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = cursor.fetchall()
print("Tables:", tables)

# Check entity_id format
cursor.execute("SELECT entity_id FROM formula_validation_logs LIMIT 5")
entity_ids = cursor.fetchall()
print("\nentity_id samples:", entity_ids)

# Check sent_id format
cursor.execute("SELECT sent_id FROM sentences LIMIT 5")
sent_ids = cursor.fetchall()
print("\nsent_id samples:", sent_ids)

cursor.close()
conn.close()
