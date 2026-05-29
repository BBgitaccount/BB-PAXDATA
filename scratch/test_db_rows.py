import sqlite3
from pathlib import Path


def test_db():
    db_path = Path("bb-paxdata.db")
    if not db_path.exists():
        print("Database does not exist.")
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("--- Bilateral Sentiments containing 'Türkiye' or similar ---")
    cursor.execute("SELECT DISTINCT from_country, to_country FROM bilateral_sentiments")
    for row in cursor.fetchall():
        if "rkiye" in row[1] or any(ord(c) > 127 for c in row[1]):
            print(repr(row))

    print("\n--- Country Pair Sentiment containing 'Türkiye' or similar ---")
    cursor.execute(
        "SELECT DISTINCT from_country, to_country FROM country_pair_sentiment"
    )
    for row in cursor.fetchall():
        if "rkiye" in row[1] or any(ord(c) > 127 for c in row[1]):
            print(repr(row))

    conn.close()


if __name__ == "__main__":
    test_db()
