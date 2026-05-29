import sqlite3


def main():
    conn = sqlite3.connect("bb-paxdata.db")
    cur = conn.cursor()

    panel_id = "11_hakan_fidan"
    print(f"=== INSPECTING {panel_id} ===")

    total = cur.execute(
        "SELECT COUNT(*) FROM words WHERE panel_id = ?", (panel_id,)
    ).fetchone()[0]
    diplo = cur.execute(
        "SELECT COUNT(*) FROM words WHERE panel_id = ? AND diplo_score > 0", (panel_id,)
    ).fetchone()[0]
    ne = cur.execute(
        "SELECT COUNT(*) FROM words WHERE panel_id = ? AND is_named_entity = 1",
        (panel_id,),
    ).fetchone()[0]

    punc_count = 0
    punctuation_chars = [",", ".", "!", "?", ";", ":", "(", ")", '"', "'"]

    words = cur.execute(
        "SELECT word_norm FROM words WHERE panel_id = ?", (panel_id,)
    ).fetchall()
    for (w,) in words:
        if any(char in w for char in punctuation_chars):
            punc_count += 1

    print(f"Total words: {total}")
    print(f"Words with diplo_score > 0: {diplo}")
    print(f"Words marked as named entity: {ne}")
    print(f"Words containing punctuation characters: {punc_count}")

    # Sample words
    all_samples = cur.execute(
        "SELECT word_raw, word_norm, diplo_score, is_named_entity FROM words WHERE panel_id = ? LIMIT 20",
        (panel_id,),
    ).fetchall()
    print("Sample records (raw, norm, diplo, is_ne):")
    for r in all_samples:
        print(r)

    conn.close()


if __name__ == "__main__":
    main()
