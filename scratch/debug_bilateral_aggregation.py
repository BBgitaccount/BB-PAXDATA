import asyncio
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.abspath("src"))

from bb_paxdata.application.use_cases.aggregate_bilateral_sentiment import (
    AggregateBilateralSentimentInput,
    AggregateBilateralSentimentUseCase,
)
from bb_paxdata.infrastructure.db.repositories.country_repository import (
    BilateralSentimentRepository,
    CountryReferenceRepository,
)
from bb_paxdata.infrastructure.db.session import SessionLocal


async def debug_agg():
    async with SessionLocal() as session:
        ref_repo = CountryReferenceRepository(session)
        sentiment_repo = BilateralSentimentRepository(session)

        panel_id = "01_ahmed_al-sharaa"
        references = await ref_repo.get_by_panel(panel_id)
        print(f"Found {len(references)} references for panel {panel_id}")

        use_case = AggregateBilateralSentimentUseCase(ref_repo, sentiment_repo)
        res = await use_case.execute(
            AggregateBilateralSentimentInput(panel_id=panel_id)
        )
        print("Aggregation Output:")
        print(f"  Created: {res.created_count}")
        print(f"  Updated: {res.updated_count}")
        print(f"  Total Pairs: {res.total_pairs}")
        print(f"  Errors: {res.errors}")

        # Commit to see if it saves
        await session.commit()
        print("Transaction committed.")


if __name__ == "__main__":
    asyncio.run(debug_agg())
