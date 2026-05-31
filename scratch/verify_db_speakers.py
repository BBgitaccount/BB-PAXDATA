import sqlite3
import sys


def main():
    # Configure stdout to handle UTF-8 to prevent cp1252 encoding errors on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    conn = sqlite3.connect("bb-paxdata.db")
    cursor = conn.cursor()

    print("Querying Speaker Profiles from database...")
    cursor.execute("SELECT DISTINCT emotion_category FROM sentences")
    print("Unique emotion categories in sentences table:", cursor.fetchall())
    print("-" * 80)
    cursor.execute(
        """
        SELECT 
            speaker_id, 
            full_name, 
            country, 
            power_level, 
            influence_tier,
            cooperative_pct,
            constructive_pct,
            neutral_pct,
            concerned_pct,
            confrontational_pct,
            risk_event_count,
            dominant_emotion,
            dominant_topic,
            top_topics,
            dominant_frame
        FROM speaker_profiles
        """
    )
    rows = cursor.fetchall()
    print(f"Found {len(rows)} speaker profiles in database.")
    print("=" * 80)
    for row in rows:
        print(f"ID: {row[0]}")
        print(f"  Name: {row[1]}")
        print(f"  Country: {row[2]}")
        print(f"  Power Level: {row[3]}")
        print(f"  Influence Tier: {row[4]}")
        print(f"  Cooperative Pct: {row[5]:.2%}")
        print(f"  Constructive Pct: {row[6]:.2%}")
        print(f"  Neutral Pct: {row[7]:.2%}")
        print(f"  Concerned Pct: {row[8]:.2%}")
        print(f"  Confrontational Pct: {row[9]:.2%}")
        print(f"  Risk Event Count: {row[10]}")
        print(f"  Dominant Emotion: {row[11]}")
        print(f"  Dominant Topic: {row[12]}")
        print(f"  Top Topics: {row[13]}")
        print(f"  Dominant Frame: {row[14]}")
        print("-" * 80)

    conn.close()


if __name__ == "__main__":
    main()
