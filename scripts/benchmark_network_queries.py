"""Benchmark database recursive CTE traversals to evaluate Neo4j requirements."""

import asyncio
import time

from bb_paxdata.infrastructure.db.session import SessionLocalCLI
from sqlalchemy import text

QUERIES = [
    # Multi-hop actor-to-concept influence (2-hop)
    """
    WITH RECURSIVE network AS (
        SELECT actor_id, concept_id, 1 AS depth
        FROM discourse_network_edges
        WHERE actor_id = :start
        UNION ALL
        SELECT e.actor_id, e.concept_id, n.depth + 1
        FROM discourse_network_edges e
        JOIN network n ON e.actor_id = n.concept_id
        WHERE n.depth < 2
    )
    SELECT DISTINCT concept_id, depth FROM network
    """,
    # Actor degree distribution (out degree approximation)
    "SELECT actor_id, COUNT(*) as out_degree FROM discourse_network_edges GROUP BY actor_id ORDER BY out_degree DESC LIMIT 20",
]


async def benchmark() -> None:
    print("Starting network queries traversal benchmark...")
    async with SessionLocalCLI() as db:
        for i, q in enumerate(QUERIES):
            t0 = time.monotonic()
            try:
                await db.execute(text(q), {"start": "TURKEY"})
                elapsed = time.monotonic() - t0
                print(f"Query {i+1} completed in: {elapsed*1000:.1f}ms")
            except Exception as e:
                print(f"Query {i+1} failed: {e}")


if __name__ == "__main__":
    asyncio.run(benchmark())
