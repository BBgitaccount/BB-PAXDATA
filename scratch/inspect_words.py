import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    diplo = cur.execute("SELECT COUNT(*) FROM words WHERE diplo_score > 0").fetchone()[
        0
    ]
    ne = cur.execute("SELECT COUNT(*) FROM words WHERE is_named_entity = 1").fetchone()[
        0
    ]

    punc_count = 0
    punctuation_chars = [",", ".", "!", "?", ";", ":", "(", ")", '"', "'"]

    words = cur.execute("SELECT word_norm FROM words").fetchall()
    for (w,) in words:
        if any(char in w for char in punctuation_chars):
            punc_count += 1

    print(f"Total words: {total}")
    print(f"Words with diplo_score > 0: {diplo}")
    print(f"Words marked as named entity: {ne}")
    print(f"Words containing punctuation characters: {punc_count}")

    # Sample punctuation words
    punc_samples = []
    for (w,) in words:
        if any(char in w for char in punctuation_chars):
            punc_samples.append(w)
            if len(punc_samples) >= 15:
                break
    print(f"Sample punctuation words: {punc_samples}")

    # Sample named entity words
    ne_samples = cur.execute(
        "SELECT word_norm FROM words WHERE is_named_entity = 1 LIMIT 15"
    ).fetchall()
    print(f"Sample named entities: {[x[0] for x in ne_samples]}")

    conn.close()


if __name__ == "__main__":
    main()
