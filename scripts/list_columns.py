import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import asyncpg


async def main():
    url = os.environ["DATABASE_URL"]
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    conn = await asyncpg.connect(url)

    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name='sentences' ORDER BY ordinal_position"
    )
    print("sentences columns:")
    for r in rows:
        print(" ", r["column_name"])

    rows2 = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name='ai_sentence_analysis' ORDER BY ordinal_position"
    )
    print("ai_sentence_analysis columns:")
    for r in rows2:
        print(" ", r["column_name"])

    await conn.close()


asyncio.run(main())
