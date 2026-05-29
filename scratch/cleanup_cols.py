import sqlite3

conn = sqlite3.connect("bb-paxdata.db")
cursor = conn.cursor()
# Drop the view v_diplomatic_network to ensure it doesn't block renames
try:
    cursor.execute("DROP VIEW IF EXISTS v_diplomatic_network")
    print("Dropped view v_diplomatic_network")
except Exception as e:
    print(f"Error dropping view: {e}")

for col in [
    "pattern_subtype",
    "matched_keyword",
    "prev_sentence",
    "next_sentence",
    "risk_score",
    "sentiment_category",
    "created_at",
]:
    try:
        cursor.execute(f"ALTER TABLE pattern_records DROP COLUMN {col}")
        print(f"Dropped {col}")
    except Exception as e:
        print(f"Could not drop {col}: {e}")
conn.commit()
conn.close()
