import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cur = conn.cursor()

    panel_id = "11_hakan_fidan"
    print(f"=== VADER_COMPOUND DISTRIBUTION IN SENTENCES FOR {panel_id} ===")

    # Query vader_compound values
    vals = cur.execute(
        "SELECT vader_compound, COUNT(*) FROM sentences WHERE panel_id = ? GROUP BY vader_compound ORDER BY vader_compound",
        (panel_id,),
    ).fetchall()

    for val, count in vals:
        print(f"Value: {val:<10} | Count: {count}")

    # Print first 20 sentence compounds and texts
    print("\nSample records:")
    samples = cur.execute(
        "SELECT sent_id, vader_compound, text FROM sentences WHERE panel_id = ? LIMIT 20",
        (panel_id,),
    ).fetchall()
    for row in samples:
        print(f"ID: {row[0]:<20} | Score: {row[1]:<10} | Text: {row[2][:80]}...")

    conn.close()


if __name__ == "__main__":
    main()
