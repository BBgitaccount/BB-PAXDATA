import json
import sqlite3
from collections import Counter

db_path = "bb-paxdata.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Clear table
c.execute("DELETE FROM country_stats")
print("Cleared country_stats table.")

c.execute(
    "SELECT file_id, country, word_count, sentence_count, duration_sec, diplo_compound, emotion_category, topic_scores FROM segments"
)
rows = c.fetchall()

groups = {}
for r in rows:
    (
        file_id,
        country,
        word_count,
        sentence_count,
        duration_sec,
        diplo_compound,
        emotion_category,
        topic_scores_raw,
    ) = r
    if not country or country in ("—", "Unknown", "unknown", ""):
        continue
    key = (country, file_id)
    if key not in groups:
        groups[key] = []
    groups[key].append(r)

print(f"Total groups in Python: {len(groups)}")

inserted_keys = []
for (country, file_id), grp in groups.items():
    n_segs = len(grp)
    sents = sum(s[3] or 0 for s in grp)
    words = sum(s[2] or 0 for s in grp)
    dur = sum(s[4] or 0 for s in grp)

    diplo_compounds = [s[5] for s in grp if s[5] is not None]
    avg_s = (
        round(sum(diplo_compounds) / len(diplo_compounds), 4)
        if diplo_compounds
        else 0.0
    )

    emos = [s[6] for s in grp if s[6]]
    dom_emo = Counter(emos).most_common(1)[0][0] if emos else None

    all_ts = Counter()
    for s in grp:
        ts_raw = s[7]
        if ts_raw:
            try:
                ts = json.loads(ts_raw)
                if isinstance(ts, dict):
                    for t, sc in ts.items():
                        all_ts[t] += float(sc or 0.0)
            except Exception:
                pass

    dom_topic = all_ts.most_common(1)[0][0] if all_ts else None
    wpm = round(words / (dur / 60.0), 1) if dur > 0 else 0.0

    key_str = f"({country}, {file_id})"
    try:
        c.execute(
            """INSERT OR REPLACE INTO country_stats
               (country, file_id, n_segments, n_sentences, total_words, total_duration_sec,
                words_per_minute, avg_sentiment, dominant_emotion, dominant_topic, topic_scores)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                country,
                file_id,
                n_segs,
                sents,
                words,
                dur,
                wpm,
                avg_s,
                dom_emo,
                dom_topic,
                json.dumps(dict(all_ts.most_common(5))),
            ),
        )
        # Check if row count increased
        c.execute("SELECT COUNT(*) FROM country_stats")
        cnt = c.fetchone()[0]
        print(
            f"Inserted: {key_str.encode('ascii', errors='replace').decode()} -> Current row count: {cnt}"
        )
    except Exception as e:
        print(f"FAILED: {key_str.encode('ascii', errors='replace').decode()} -> {e}")

conn.commit()
conn.close()
