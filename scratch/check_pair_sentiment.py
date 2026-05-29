import sqlite3


def check_pair_sentiment(db_path):
    print("\n==========================================")
    print(f"DB: {db_path}")
    print("==========================================")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Check table schema
    c.execute("SELECT sql FROM sqlite_master WHERE name='country_pair_sentiment'")
    schema = c.fetchone()
    if schema:
        print("Schema:")
        print(schema[0])
    else:
        print("Table country_pair_sentiment does not exist!")
        conn.close()
        return

    # Check count
    c.execute("SELECT COUNT(*) FROM country_pair_sentiment")
    count = c.fetchone()[0]
    print(f"Row count: {count}")

    # Check first 5 rows
    c.execute("SELECT * FROM country_pair_sentiment LIMIT 5")
    rows = c.fetchall()
    print("Sample rows:")
    for r in rows:
        print(r)

    conn.close()


check_pair_sentiment("bb-paxdata.db")
check_pair_sentiment("bb-paxdata-temp.db")
