import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cursor = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='view'")
    for name, sql in cursor.fetchall():
        print(f"View: {name}")
        print(f"SQL: {sql}\n" + "-" * 50)
    conn.close()


if __name__ == "__main__":
    main()
