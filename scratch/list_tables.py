import sqlite3


def check_db(name):
    print(f"=== DB: {name} ===")
    conn = sqlite3.connect(name)
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    print("Tables:", tables)
    conn.close()


check_db("bb-paxdata.db")
check_db("bb-paxdata.db.bak")
