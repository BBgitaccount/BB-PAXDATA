import json
import sqlite3
from collections import Counter


def heal_db(db_path: str):
    print(f"\nHealing database: {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='segments'"
        )
        if not c.fetchone():
            print(f"Table 'segments' does not exist in {db_path}. Skipping.")
            conn.close()
            return

        # Dynamically determine file_id / panel_id column names
        c.execute("PRAGMA table_info(segments)")
        seg_cols = [col[1] for col in c.fetchall()]
        file_id_col = "file_id" if "file_id" in seg_cols else "panel_id"

        c.execute("PRAGMA table_info(country_stats)")
        cs_cols = [col[1] for col in c.fetchall()]
        cs_file_id_col = "file_id" if "file_id" in cs_cols else "panel_id"

        c.execute("PRAGMA table_info(topic_matrix)")
        tm_cols = [col[1] for col in c.fetchall()]
        tm_file_id_col = "file_id" if "file_id" in tm_cols else "panel_id"

        # Clear existing tables
        c.execute("DELETE FROM country_stats")
        c.execute("DELETE FROM topic_matrix")

        c.execute(
            f"SELECT {file_id_col}, country, word_count, sentence_count, duration_sec, diplo_compound, emotion_category, topic_scores FROM segments"
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

            topic_scores = {}
            if topic_scores_raw:
                try:
                    topic_scores = json.loads(topic_scores_raw)
                except Exception:
                    pass

            groups[key].append(
                {
                    "word_count": word_count or 0,
                    "sentence_count": sentence_count or 0,
                    "duration_sec": duration_sec or 0,
                    "diplo_compound": diplo_compound,
                    "emotion_category": emotion_category,
                    "topic_scores": topic_scores,
                }
            )

        print(f"Found {len(groups)} country-file groups to process.")

        cs_count = 0
        tm_count = 0

        for (country, file_id), grp in groups.items():
            n_segs = len(grp)
            sents = sum(s["sentence_count"] for s in grp)
            words = sum(s["word_count"] for s in grp)
            dur = sum(s["duration_sec"] for s in grp)

            diplo_compounds = [
                s["diplo_compound"] for s in grp if s["diplo_compound"] is not None
            ]
            avg_s = (
                round(sum(diplo_compounds) / len(diplo_compounds), 4)
                if diplo_compounds
                else 0.0
            )

            emos = [s["emotion_category"] for s in grp if s["emotion_category"]]
            dom_emo = Counter(emos).most_common(1)[0][0] if emos else None

            all_ts = Counter()
            for s in grp:
                if s["topic_scores"]:
                    if isinstance(s["topic_scores"], dict):
                        for t, sc in s["topic_scores"].items():
                            all_ts[t] += float(sc or 0.0)

            dom_topic = all_ts.most_common(1)[0][0] if all_ts else None
            wpm = round(words / (dur / 60.0), 1) if dur > 0 else 0.0

            c.execute(
                f"""INSERT OR REPLACE INTO country_stats
                   (country, {cs_file_id_col}, n_segments, n_sentences, total_words, total_duration_sec,
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
                    json.dumps(dict(all_ts.most_common(5)), ensure_ascii=False),
                ),
            )
            cs_count += 1

            for topic, score in all_ts.items():
                if score > 0.0:
                    c.execute(
                        f"""INSERT OR REPLACE INTO topic_matrix
                           ({tm_file_id_col}, country, topic, score)
                           VALUES (?, ?, ?, ?)""",
                        (file_id, country, topic, float(score)),
                    )
                    tm_count += 1

        conn.commit()
        print(
            f"Successfully updated {cs_count} country_stats and {tm_count} topic_matrix rows in {db_path}."
        )
        conn.close()
    except Exception as e:
        print(f"Error healing database {db_path}: {e}")


if __name__ == "__main__":
    heal_db("bb-paxdata.db")
    heal_db("bb-paxdata-temp.db")
