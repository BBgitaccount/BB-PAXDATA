import os
import sqlite3
import sys

# Ensure UTF-8 printing
reconfigure = getattr(sys.stdout, "reconfigure", None)
if reconfigure is not None:
    reconfigure(encoding="utf-8")

db_old_path = r"C:\Users\THINKPAD\Desktop\Yazılım\BB-PAXDATA\bbdbda.db"
db_new_path = r"c:\Users\THINKPAD\Desktop\BB-PAXDATA\paxdata.db"


def inspect_db(name, path):
    print("\n==================================================")
    print(f"INSPECTING DATABASE: {name}")
    try:
        print(f"Path: {path}")
    except Exception:
        print("Path: (contains unicode chars)")

    if not os.path.exists(path):
        print("Error: File does not exist!")
        return
    print(f"Size: {os.path.getsize(path)} bytes")

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables ({len(tables)}): {', '.join(tables)}")

    # Get row counts
    print("\nRow Counts:")
    for table in sorted(tables):
        if table.startswith("sqlite_"):
            continue
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`;")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count}")
        except Exception as e:
            print(f"  {table}: Error: {e}")

    # Check null/empty stats in important tables
    print("\nData Density check:")
    if "sentences" in tables:
        try:
            cursor.execute("SELECT COUNT(*) FROM sentences;")
            total_sents = cursor.fetchone()[0]
            if total_sents > 0:
                cursor.execute("PRAGMA table_info(sentences);")
                cols = [r[1] for r in cursor.fetchall()]
                print(f"  Sentences columns count: {len(cols)}")

                checks = [
                    "dominant_topic",
                    "risk_score",
                    "negation_aware_diplo",
                    "dominant_frame",
                    "vader_compound",
                    "diplo_compound",
                    "hedging_score",
                    "politeness_ratio",
                    "face_threat_count",
                    "face_save_count",
                    "evidence_types",
                    "appraisal_attitude",
                    "audience_type",
                ]
                for check in checks:
                    if check in cols:
                        cursor.execute(
                            f"SELECT COUNT(*) FROM sentences WHERE `{check}` IS NOT NULL AND `{check}` != '' AND `{check}` != 0 AND `{check}` != 0.0;"
                        )
                        filled = cursor.fetchone()[0]
                        print(
                            f"    {check} filled (non-zero/non-null): {filled}/{total_sents} ({filled / total_sents * 100:.1f}%)"
                        )
                    else:
                        print(f"    {check} column does not exist!")
        except Exception as e:
            print(f"  Sentences check error: {e}")

    # Check if there are other tables like risk_events, demand_records etc.
    other_tables = [
        "risk_events",
        "demand_records",
        "pattern_records",
        "panel_dynamics",
        "discourse_network_edges",
        "ai_sentence_analysis",
    ]
    for ot in other_tables:
        if ot in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM `{ot}`;")
                cnt = cursor.fetchone()[0]
                print(f"  Table `{ot}` row count: {cnt}")
            except Exception as e:
                print(f"  Table `{ot}` error: {e}")

    conn.close()


inspect_db("OLD SYSTEM DATABASE", db_old_path)
inspect_db("NEW SYSTEM DATABASE", db_new_path)
