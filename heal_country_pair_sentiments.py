import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add src folder to python path to allow imports from bb_paxdata package
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def heal_db(db_path: Path) -> None:
    if not db_path.exists():
        print(f"Database not found at: {db_path}")
        return

    print(f"\nProcessing database: {db_path}")
    db_url = f"sqlite+aiosqlite:///{db_path.resolve()}"
    engine = create_async_engine(db_url, echo=False, future=True)
    async_session = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        from bb_paxdata.infrastructure.db.repositories.country_repository import (
            BilateralSentimentRepository,
        )

        repo = BilateralSentimentRepository(session)
        print("Rebuilding country_pair_sentiment aggregates...")
        await repo.rebuild_global_country_pair_sentiments()
        await session.commit()
        print("Successfully backfilled country pair sentiment records.")
    await engine.dispose()


def main():
    root_dir = Path(__file__).parent.resolve()
    db_paths = [root_dir / "bb-paxdata.db", root_dir / "bb-paxdata-temp.db"]
    for db_path in db_paths:
        asyncio.run(heal_db(db_path))


if __name__ == "__main__":
    main()
