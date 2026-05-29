import sqlite3


def check_triggers(db_path):
    print(f"\n--- Checking Triggers in DB: {db_path} ---")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger'")
    triggers = c.fetchall()
    print(f"Triggers ({len(triggers)}):")
    for t in triggers:
        print(f"  Trigger: {t[0]} on {t[1]}")

    conn.close()


check_triggers("bb-paxdata.db")
