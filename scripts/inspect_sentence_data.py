import sqlite3


def main():
    conn = sqlite3.connect("paxdata.db")
    cursor = conn.cursor()

    # Emotion categories in sentences
    print("--- Sentence Emotion Categories ---")
    cursor.execute(
        "SELECT emotion_category, COUNT(*) FROM sentences GROUP BY emotion_category"
    )
    for row in cursor.fetchall():
        print(row)

    # Rhetoric types in sentences
    print("\n--- Sentence Rhetoric Types ---")
    cursor.execute(
        "SELECT rhetoric_type, COUNT(*) FROM sentences GROUP BY rhetoric_type"
    )
    for row in cursor.fetchall():
        print(row)

    # Demand types in sentences
    print("\n--- Sentence Demand Types ---")
    cursor.execute("SELECT demand_type, COUNT(*) FROM sentences GROUP BY demand_type")
    for row in cursor.fetchall():
        print(row)

    conn.close()


if __name__ == "__main__":
    main()
