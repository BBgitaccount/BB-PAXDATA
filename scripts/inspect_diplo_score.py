import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cursor = conn.cursor()

    # Check diplo_score on words
    cursor.execute("SELECT COUNT(*) FROM words WHERE diplo_score != 0")
    print("Words with non-zero diplo_score count:", cursor.fetchone()[0])

    conn.close()


if __name__ == "__main__":
    main()
