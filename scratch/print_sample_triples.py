import sqlite3


def print_samples():
    conn = sqlite3.connect("bb-paxdata.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM dependency_triples")
    total = cursor.fetchone()[0]
    print(f"Total rows in dependency_triples: {total}")

    if total > 0:
        print("\n--- Sample Triples (First 10 rows) ---")
        cursor.execute(
            """
            SELECT triple_id, file_id, speaker_name, subject_raw, subject_resolved, 
                   verb_lemma, object_raw, object_resolved, is_passive, is_negative, sentiment_context
            FROM dependency_triples 
            LIMIT 10
        """
        )
        rows = cursor.fetchall()
        for r in rows:
            print(f"ID: {r[0]} | File: {r[1]} | Speaker: {r[2]}")
            print(f"  Subject: '{r[3]}' -> Resolved: '{r[4]}'")
            print(f"  Verb:    '{r[5]}' (Passive: {bool(r[8])}, Negated: {bool(r[9])})")
            print(f"  Object:  '{r[6]}' -> Resolved: '{r[7]}'")
            print(f"  Sentiment Context: {r[10]}")
            print("-" * 50)

    conn.close()


if __name__ == "__main__":
    print_samples()
