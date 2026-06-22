# scripts/normalize_countries.py

from sqlalchemy import create_engine, inspect, text

from bb_paxdata.application.domain.lexicon.country_bloc_mapping import normalize_country
from bb_paxdata.config.settings import get_settings


def main():
    settings = get_settings()
    db_url = settings.database_url or "sqlite+aiosqlite:///paxdata.db"
    sync_url = db_url.replace("sqlite+aiosqlite", "sqlite").replace(
        "postgresql+asyncpg", "postgresql"
    )

    print("=== STARTING COUNTRY NORMALIZATION ===")
    print(f"Connecting to database via: {sync_url}")
    engine = create_engine(sync_url)
    inspector = inspect(engine)

    # 1. Target tables and columns containing country codes or names
    targets = {
        "speakers": ["country_code", "country_name"],
        "speaker_profiles": ["country"],
        "segments": ["country"],
        "sentences": ["country"],
        "words": ["country"],
        "bilateral_sentiments": ["from_country", "to_country"],
        "country_references": ["speaker_country", "referenced_country"],
        "discourse_flows": ["from_country", "to_country"],
        "country_stats": ["country"],
        "demand_records": ["country"],
        "dependency_triples": ["country"],
        "panel_dynamics": ["country"],
        "pattern_records": ["country"],
        "segment_events": ["country"],
        "topic_matrix": ["country"],
    }

    # 2. Backup the tables first
    print("\n--- CREATING BACKUP TABLES ---")
    with engine.connect() as conn:
        for table in targets.keys():
            if inspector.has_table(table):
                backup_table = f"{table}_backup_2026"
                print(f"Backing up '{table}' to '{backup_table}'...")
                conn.execute(text(f'DROP TABLE IF EXISTS "{backup_table}" CASCADE'))
                conn.execute(
                    text(f'CREATE TABLE "{backup_table}" AS SELECT * FROM "{table}"')
                )
        conn.commit()

    # 3. Standardize and update
    print("\n--- UPDATING COUNTRY RECORDS ---")
    with engine.connect() as conn:
        for table, columns in targets.items():
            if not inspector.has_table(table):
                print(f"Table '{table}' does not exist, skipping.")
                continue

            print(f"Processing table '{table}'...")
            for col in columns:
                # Find distinct values in this column
                try:
                    res = conn.execute(
                        text(
                            f'SELECT DISTINCT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL'
                        )
                    )
                    distinct_vals = [r[0] for r in res.fetchall()]
                except Exception as e:
                    print(
                        f"  Error fetching distinct values for '{col}' in '{table}': {e}"
                    )
                    continue

                for val in distinct_vals:
                    if not val:
                        continue

                    # Normalize
                    iso3, std_name, _ = normalize_country(str(val))
                    if iso3 != "UNK":
                        # If the column is country_code, we use iso3. Otherwise standard full name.
                        new_val = iso3 if col == "country_code" else std_name
                        if val != new_val:
                            print(
                                f"  Updating '{table}'.'{col}': '{val}' -> '{new_val}'"
                            )
                            try:
                                conn.execute(
                                    text(
                                        f'UPDATE "{table}" SET "{col}" = :new_val WHERE "{col}" = :old_val'
                                    ),
                                    {"new_val": new_val, "old_val": val},
                                )
                            except Exception as e:
                                print(
                                    f"    Error updating value '{val}' in '{table}': {e}"
                                )
        conn.commit()

    # 4. Verify results
    print("\n--- VERIFICATION OF NORMALIZE_COUNTRIES ---")
    with engine.connect() as conn:
        # Check speakers table
        if inspector.has_table("speakers"):
            print("\nSpeakers table country name distribution:")
            res = conn.execute(
                text(
                    "SELECT country_name, count(*) FROM speakers GROUP BY country_name ORDER BY count(*) DESC LIMIT 20"
                )
            )
            for r in res.fetchall():
                print(f"  {r[0]}: {r[1]}")

            # Check length < 4 names (excluding None/Unknown)
            print("\nChecking for short country names in speakers:")
            res = conn.execute(
                text(
                    "SELECT DISTINCT country_name FROM speakers WHERE length(country_name) < 4 AND country_name NOT IN ('BM', 'UN', 'EU')"
                )
            )
            shorts = [r[0] for r in res.fetchall()]
            if shorts:
                print(f"  Warning! Short names still exist: {shorts}")
            else:
                print("  Success: No short names left in country_name column!")

    print("\n=== COUNTRY NORMALIZATION COMPLETED ===")


if __name__ == "__main__":
    main()
