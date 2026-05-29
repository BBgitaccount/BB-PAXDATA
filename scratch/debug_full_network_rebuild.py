import asyncio
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.abspath("src"))

from bb_paxdata.infrastructure.db.session import SessionLocal
from bb_paxdata.interfaces.cli.commands.build import rebuild_network_for_file


async def debug_rebuild():
    async with SessionLocal() as session:
        panel_id = "01_ahmed_al-sharaa"
        try:
            print(f"Running rebuild_network_for_file for panel {panel_id}...")
            await rebuild_network_for_file(session, panel_id)
            await session.commit()
            print("Rebuild completed successfully and transaction committed!")
        except Exception as e:
            print(f"Error during rebuild: {e}")
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(debug_rebuild())
