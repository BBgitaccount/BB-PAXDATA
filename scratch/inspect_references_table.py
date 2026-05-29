import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cur = conn.cursor()

    rows = cur.execute("SELECT * FROM country_references LIMIT 10").fetchall()
    cols = [description[0] for description in cur.description]
    print("Columns:", cols)
    print("Rows:")
    for r in rows:
        print(r)

    conn.close()


if __name__ == "__main__":
    main()
