import sqlite3


def inspect():
    conn = sqlite3.connect("bb-paxdata.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files LIMIT 5;")
    cols = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    print("Columns:", cols)
    for r in rows:
        print(dict(zip(cols, r)))
    conn.close()


if __name__ == "__main__":
    inspect()
