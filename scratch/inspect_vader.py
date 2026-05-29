import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cur = conn.cursor()

    # Query vader_compound values
    vals = cur.execute(
        "SELECT vader_compound, COUNT(*) FROM sentences GROUP BY vader_compound"
    ).fetchall()
    print("=== VADER_COMPOUND DISTRIBUTION IN SENTENCES ===")
    for val, count in vals:
        print(f"Value: {val:<10} | Count: {count}")

    conn.close()


if __name__ == "__main__":
    main()
