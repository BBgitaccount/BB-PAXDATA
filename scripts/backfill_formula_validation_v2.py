"""Backfill existing formula_validation_logs records with v2 fields.

Sets is_current=True and log_version=1 for all existing records
that were created before the HITL v2 migration.

Usage:
    python scripts/backfill_formula_validation_v2.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

load_dotenv()


async def backfill() -> None:
    """Backfill all existing FormulaValidationLog records with v2 defaults."""
    # Use the same settings as alembic/env.py
    from bb_paxdata.config.settings import get_settings

    settings = get_settings()
    database_url = settings.database_url or os.getenv(
        "DATABASE_URL", "sqlite:///./data/paxdata.db"
    )

    # Convert sync URL to async
    if database_url.startswith("sqlite:///"):
        async_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    elif database_url.startswith("postgresql://"):
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        async_url = database_url

    engine = create_async_engine(async_url, echo=False)

    async with engine.begin() as conn:
        # Set is_current=True for all records where it is NULL
        result1 = await conn.execute(
            text(
                "UPDATE formula_validation_logs "
                "SET is_current = 1 "
                "WHERE is_current IS NULL"
            )
        )
        print(f"  -> is_current backfilled: {result1.rowcount} rows")

        # Set log_version=1 for all records where it is NULL
        result2 = await conn.execute(
            text(
                "UPDATE formula_validation_logs "
                "SET log_version = 1 "
                "WHERE log_version IS NULL"
            )
        )
        print(f"  -> log_version backfilled: {result2.rowcount} rows")

    await engine.dispose()
    print("\n[OK] Backfill complete!")


if __name__ == "__main__":
    print("[*] Backfilling formula_validation_logs with v2 defaults...")
    asyncio.run(backfill())
