import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM sentences").fetchone()[0]
    print(f"Total rows in sentences: {total}")

    cols = [r[1] for r in cur.execute("PRAGMA table_info(sentences)").fetchall()]

    for c in cols:
        # Check how many are empty/default
        null_count = cur.execute(
            f"SELECT COUNT(*) FROM sentences WHERE {c} IS NULL"
        ).fetchone()[0]
        zero_count = cur.execute(
            f"SELECT COUNT(*) FROM sentences WHERE {c} = 0 OR {c} = 0.0"
        ).fetchone()[0]
        empty_str_count = cur.execute(
            f"SELECT COUNT(*) FROM sentences WHERE {c} = ''"
        ).fetchone()[0]
        empty_json_count = cur.execute(
            f"SELECT COUNT(*) FROM sentences WHERE {c} = '{{}}' OR {c} = '[]'"
        ).fetchone()[0]

        total_empty = cur.execute(
            f"""
            SELECT COUNT(*) FROM sentences 
            WHERE {c} IS NULL 
               OR {c} = 0 
               OR {c} = 0.0 
               OR {c} = '' 
               OR {c} = '{{}}' 
               OR {c} = '[]'
        """
        ).fetchone()[0]

        pct = (total_empty / total) * 100 if total else 0
        print(
            f"Column: {c:<25} | Null: {null_count:<5} | Zero: {zero_count:<5} | EmptyStr: {empty_str_count:<5} | EmptyJSON: {empty_json_count:<5} | Total Empty: {total_empty:<5} ({pct:.1f}%)"
        )

    conn.close()


if __name__ == "__main__":
    main()
