import sqlite3


def main():
    conn = sqlite3.connect("paxdata.db")
    cur = conn.cursor()
    tables = [
        t[0]
        for t in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    for t in sorted(tables):
        count = cur.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
        if count > 0:
            print(f"{t}: {count}")
    conn.close()


if __name__ == "__main__":
    main()
