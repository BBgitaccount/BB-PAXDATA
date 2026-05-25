import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cursor = conn.cursor()

    # Check unique sentence_index in country_references
    cursor.execute(
        "SELECT sentence_index, COUNT(*) FROM country_references GROUP BY sentence_index"
    )
    print("CountryReferences sentence_index counts:")
    for row in cursor.fetchall():
        print(row)

    conn.close()


if __name__ == "__main__":
    main()
