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
    cursor.execute(
        "SELECT DISTINCT from_country, to_country FROM bilateral_sentiments WHERE to_country LIKE '%rkiye%' OR to_country LIKE '%rkiye%'"
    )
    for row in cursor.fetchall():
        print(row)

    print("\n--- Country Pair Sentiment containing 'Türkiye' or similar ---")
    cursor.execute(
        "SELECT DISTINCT from_country, to_country FROM country_pair_sentiment WHERE to_country LIKE '%rkiye%' OR to_country LIKE '%rkiye%'"
    )
    for row in cursor.fetchall():
        print(row)

    conn.close()


if __name__ == "__main__":
    test_db()
