import sqlite3


def debug_db(db_path):
    print("\n==========================================")
    print(f"Debugging DB: {db_path}")
    print("==========================================")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Check if bilateral_sentiments exists and has rows
    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='bilateral_sentiments'"
    )
    if not c.fetchone():
        print("Table 'bilateral_sentiments' does not exist!")
        conn.close()
        return

    c.execute("SELECT COUNT(*) FROM bilateral_sentiments")
    count_bs = c.fetchone()[0]
    print(f"bilateral_sentiments count: {count_bs}")

    # Check country_pair_sentiment count
    c.execute("SELECT COUNT(*) FROM country_pair_sentiment")
    count_cps = c.fetchone()[0]
    print(f"country_pair_sentiment count: {count_cps}")

    # Simulate aggregation query
    query = """
        SELECT 
            from_country,
            to_country,
            SUM(total_mentions),
            AVG(avg_sentiment),
            SUM(interaction_count),
            AVG(affinity_score),
            AVG(power_weighted_score),
            AVG(diplomatic_distance)
        FROM bilateral_sentiments
        GROUP BY from_country, to_country
    """
    try:
        c.execute(query)
        rows = c.fetchall()
        print(f"Aggregation query returned {len(rows)} rows.")
        if rows:
            print("First 3 aggregated rows:")
            for r in rows[:3]:
                print(r)
    except Exception as e:
        print(f"Error executing aggregation query: {e}")

    conn.close()


debug_db("bb-paxdata.db")
debug_db("bb-paxdata-temp.db")
