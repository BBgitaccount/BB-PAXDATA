# scripts/normalize_blocs.py

from sqlalchemy import create_engine, inspect, text

from bb_paxdata.application.domain.lexicon.country_bloc_mapping import normalize_country
from bb_paxdata.config.settings import get_settings


def main():
    settings = get_settings()
    db_url = settings.database_url or "sqlite+aiosqlite:///paxdata.db"
    sync_url = db_url.replace("sqlite+aiosqlite", "sqlite").replace(
        "postgresql+asyncpg", "postgresql"
    )

    print("=== STARTING BLOC NORMALIZATION ===")
    print(f"Connecting to database via: {sync_url}")
    engine = create_engine(sync_url)
    inspector = inspect(engine)

    # 1. Target tables and their country columns to resolve standard blocs
    targets = {
        "speakers": "country_name",
        "speaker_profiles": "country",
        "segments": "country",
        "sentences": "country",
        "words": "country",
    }

    # 2. Backup the tables first (if not backed up in normalize_countries.py, or do it anyway)
    print("\n--- CREATING BACKUP TABLES FOR BLOCS ---")
    with engine.connect() as conn:
        for table in targets.keys():
            if inspector.has_table(table):
                backup_table = f"{table}_bloc_backup_2026"
                print(f"Backing up '{table}' to '{backup_table}'...")
                conn.execute(text(f'DROP TABLE IF EXISTS "{backup_table}" CASCADE'))
                conn.execute(
                    text(f'CREATE TABLE "{backup_table}" AS SELECT * FROM "{table}"')
                )
        conn.commit()

    # 3. Standardize and update blocs
    print("\n--- UPDATING BLOC ASSIGNMENTS ---")
    with engine.connect() as conn:
        for table, country_col in targets.items():
            if not inspector.has_table(table):
                print(f"Table '{table}' does not exist, skipping.")
                continue

            print(f"Processing table '{table}' based on '{country_col}'...")

            # Fetch distinct country names in this table
            try:
                res = conn.execute(
                    text(
                        f'SELECT DISTINCT "{country_col}" FROM "{table}" WHERE "{country_col}" IS NOT NULL'
                    )
                )
                distinct_countries = [r[0] for r in res.fetchall()]
            except Exception as e:
                print(f"  Error fetching distinct countries for table '{table}': {e}")
                continue

            for country in distinct_countries:
                if not country:
                    continue

                # Resolve standard bloc
                iso3, _std_name, std_bloc = normalize_country(str(country))
                if iso3 != "UNK" and std_bloc:
                    # Update all records for this country in the table with the resolved bloc
                    print(
                        f"  Updating '{table}' for country '{country}' -> bloc: '{std_bloc}'"
                    )
                    try:
                        conn.execute(
                            text(
                                f'UPDATE "{table}" SET bloc = :bloc WHERE "{country_col}" = :country'
                            ),
                            {"bloc": std_bloc, "country": country},
                        )
                    except Exception as e:
                        print(
                            f"    Error updating bloc for country '{country}' in '{table}': {e}"
                        )

            # Handle unknown or null country cases to map to 'Other' or 'unknown'
            try:
                conn.execute(
                    text(
                        f'UPDATE "{table}" SET bloc = \'Other\' WHERE "{country_col}" IS NULL OR "{country_col}" = \'Unknown\''
                    )
                )
            except Exception as e:
                print(
                    f"  Error mapping null/unknown country blocs to 'Other' in '{table}': {e}"
                )

        conn.commit()

    # 4. Verify results
    print("\n--- VERIFICATION OF NORMALIZE_BLOCS ---")
    with engine.connect() as conn:
        # Check speakers bloc distribution
        if inspector.has_table("speakers"):
            print("\nSpeakers table bloc distribution:")
            res = conn.execute(
                text(
                    "SELECT bloc, count(*) FROM speakers GROUP BY bloc ORDER BY count(*) DESC"
                )
            )
            for r in res.fetchall():
                print(f"  {r[0]}: {r[1]}")

            # Check DRC specifically
            print("\nDRC Speaker bloc verification:")
            res = conn.execute(
                text(
                    "SELECT canonical_name, country_name, bloc FROM speakers WHERE country_name LIKE '%Congo%' OR country_name = 'Democratic Republic of the Congo'"
                )
            )
            for r in res.fetchall():
                print(f"  {r[0]} ({r[1]}) -> {r[2]}")

    print("\n=== BLOC NORMALIZATION COMPLETED ===")


if __name__ == "__main__":
    main()
