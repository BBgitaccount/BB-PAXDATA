from bb_paxdata.config.settings import get_settings
from sqlalchemy import create_engine, text


def main():
    settings = get_settings()
    db_url = settings.database_url or "sqlite+aiosqlite:///paxdata.db"

    # Convert async pg/sqlite URL to sync url for testing
    sync_url = db_url.replace("sqlite+aiosqlite", "sqlite").replace(
        "postgresql+asyncpg", "postgresql"
    )

    print("=== DATABASE CONNECTION TEST ===")
    print(f"DATABASE URL: {db_url}")
    print(f"SYNC URL: {sync_url}")
    print(f"DATABASE MODE: {settings.database_mode}")
    print("================================")

    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            try:
                res = conn.execute(text("SELECT version_num FROM alembic_version"))
                print(f"ALEMBIC VERSION: {res.fetchone()}")
            except Exception as e:
                print(f"Alembic version check failed/skipped: {e}")

            for table in [
                "human_reviews",
                "calibration_reports",
            ]:
                print(f"\nROW COUNT FOR {table}:")
                try:
                    r = conn.execute(text(f"SELECT count(*) FROM {table}"))
                    print(f"  {r.scalar()}")
                except Exception as e:
                    print(f"  Error reading table {table}: {e}")
        print("\nDatabase connection verified successfully!")
    except Exception as e:
        print(f"\nDatabase connection verification failed: {e}")
        raise e


if __name__ == "__main__":
    main()
