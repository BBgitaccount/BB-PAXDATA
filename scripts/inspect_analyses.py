import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

import asyncpg


async def main():
    url = os.environ["DATABASE_URL"]
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix) :]

    conn = await asyncpg.connect(url)

    # Check ai_sentence_analysis columns
    cols = await conn.fetch(
        """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'ai_sentence_analysis'
    """
    )
    print("Columns for 'ai_sentence_analysis':")
    for col in cols:
        print(f"  {col['column_name']} ({col['data_type']})")

    # Check if there is speech_act_type or action_type
    # Let's count non-null values of speech_act_type or action_type if they exist in ai_sentence_analysis or analyses
    for col in ["speech_act_type", "action_type", "speech_act", "action"]:
        try:
            val = await conn.fetchval(
                f"SELECT COUNT(*) FROM ai_sentence_analysis WHERE {col} IS NOT NULL"
            )
            print(f"ai_sentence_analysis.{col} count:", val)
        except Exception as e:
            print(f"ai_sentence_analysis.{col} error:", str(e).split("\n")[0])

    # Also search for 'speech_act_type' or 'speech_act' or 'action_type' or 'action' in 'sentences'
    for col in [
        "speech_act_type",
        "action_type",
        "speech_act",
        "action",
        "demand_type",
    ]:
        try:
            val = await conn.fetchval(
                f"SELECT COUNT(*) FROM sentences WHERE {col} IS NOT NULL"
            )
            print(f"sentences.{col} count:", val)
        except Exception as e:
            print(f"sentences.{col} error:", str(e).split("\n")[0])

    # Check if there are other columns or table structures we might want to check
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
