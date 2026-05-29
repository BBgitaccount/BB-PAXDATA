import sqlite3

db_path = "bb-paxdata.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Try with PRAGMA foreign_keys = ON;
c.execute("PRAGMA foreign_keys = ON;")

try:
    c.execute(
        """INSERT INTO country_stats
           (country, file_id, n_segments, n_sentences, total_words, total_duration_sec)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("TR", "03_erdoğan", 1, 1, 1, 1),
    )
    print("Direct INSERT succeeded!")
except Exception as e:
    print(f"Direct INSERT failed with error: {type(e).__name__}: {e}")

conn.close()
