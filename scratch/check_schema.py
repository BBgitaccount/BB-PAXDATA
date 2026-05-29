import sqlite3


def check(db_name):
    print(f"=== DB: {db_name} ===")
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    schema = c.execute(
        "SELECT sql FROM sqlite_master WHERE name='demand_records'"
    ).fetchone()
    if schema:
        print("Schema:")
        print(schema[0])

    # Check count of NULL vs non-NULL for both columns
    c.execute(
        "SELECT COUNT(*), SUM(CASE WHEN demand_category IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN target_entity IS NULL THEN 1 ELSE 0 END) FROM demand_records"
    )
    row = c.fetchone()
    print(f"Total rows: {row[0]}")
    print(f"NULL demand_category count: {row[1]}")
    print(f"NULL target_entity count: {row[2]}")

    # Check first 5 rows to see what is stored
    c.execute(
        "SELECT demand_id, sent_id, demand_verb, demand_category, target_entity, full_sentence FROM demand_records LIMIT 5"
    )
    rows = c.fetchall()
    print("Sample rows:")
    for r in rows:
        print(r)
    conn.close()


print("--- Checking BB-PAXDATA DBs ---")
check("bb-paxdata.db")
check("bb-paxdata-temp.db")
