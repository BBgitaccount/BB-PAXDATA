import sqlite3


def main():
    conn = sqlite3.connect("paxdata.db")
    cursor = conn.cursor()

    # Check country_references entries
    cursor.execute("SELECT COUNT(*) FROM country_references")
    print("CountryReferences count:", cursor.fetchone()[0])
    if cursor.fetchone():
        cursor.execute("SELECT * FROM country_references LIMIT 5")
        for row in cursor.fetchall():
            print(row)

    # Check entities_gpe in sentences
    cursor.execute(
        "SELECT COUNT(*) FROM sentences WHERE entities_gpe IS NOT NULL AND entities_gpe != ''"
    )
    print("Sentences with entities_gpe count:", cursor.fetchone()[0])

    conn.close()


if __name__ == "__main__":
    main()
