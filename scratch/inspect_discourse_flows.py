import sqlite3


def inspect():
    conn = sqlite3.connect("bb-paxdata.db")
    cursor = conn.cursor()

    tables_to_count = [
        "country_references",
        "bilateral_sentiments",
        "discourse_flows",
        "discourse_network_edges",
    ]
    for t in tables_to_count:
        try:
            cursor.execute(f"SELECT count(*) FROM {t};")
            cnt = cursor.fetchone()[0]
            print(f"{t} count: {cnt}")
        except Exception as e:
            print(f"Error checking {t}: {e}")

    conn.close()


if __name__ == "__main__":
    inspect()
