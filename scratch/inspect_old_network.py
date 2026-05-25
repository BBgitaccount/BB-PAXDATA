import sqlite3

db_old_path = r"C:\Users\THINKPAD\Desktop\Yazılım\BB-PAXDATA\bbdbda.db"
conn = sqlite3.connect(db_old_path)
cursor = conn.cursor()

try:
    cursor.execute("PRAGMA table_info(discourse_network_edges);")
    cols = cursor.fetchall()
    print("Columns of discourse_network_edges:")
    for col in cols:
        print(f"  {col[1]}: {col[2]}")

    cursor.execute("SELECT * FROM discourse_network_edges LIMIT 5;")
    rows = cursor.fetchall()
    print("\nRows of discourse_network_edges:")
    for row in rows:
        print(row)
except Exception as e:
    print(f"Error: {e}")

conn.close()
