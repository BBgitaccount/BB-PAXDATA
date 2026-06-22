"""
Offline PLAID index builder for BB-PAXDATA RAG corpus.

Usage:
    python -m bb_paxdata.scripts.build_colbert_index \
        --db-url sqlite+aiosqlite:///./paxdata.db \
        --index-path .colbert_index \
        --index-name bb_paxdata_rag \
        --chunk-size 180

Corpus source: Pulls Segment.text + Sentence.text from the database.
Passage ID convention: "segment:{segment_id}" or "sentence:{sentence_id}"

Performance expectations (CPU, ColBERT-v2, PLAID):
    - ~586,896 words corpus → ~50,000–80,000 passages (180-token chunks)
    - Index build time: ~2–4 hours on CPU (single process)
    - Index size: ~2–5 GB on disk
    - Query latency post-index: < 200ms (PLAID CPU target from task spec)
"""

import asyncio
from pathlib import Path

import typer

from bb_paxdata.application.domain.services.colbert_embedding_service import (
    RAGatoulleColBERTService,
)
from bb_paxdata.infrastructure.db.models import SegmentTable
from bb_paxdata.infrastructure.db.session import get_session

app = typer.Typer()


@app.command()
def build(
    db_url: str = typer.Option(..., help="SQLAlchemy async DB URL"),
    index_path: Path = typer.Option(Path(".colbert_index")),
    index_name: str = typer.Option("bb_paxdata_rag"),
    chunk_size: int = typer.Option(180, help="Max tokens per passage"),
    batch_size: int = typer.Option(1000, help="DB fetch batch size"),
) -> None:
    asyncio.run(_build_async(db_url, index_path, index_name, chunk_size, batch_size))


async def _build_async(
    db_url: str,
    index_path: Path,
    index_name: str,
    chunk_size: int,
    batch_size: int,
) -> None:
    passages: list[str] = []
    passage_ids: list[str] = []

    async with get_session(db_url) as session:
        # Fetch segments (primary analytical units)
        offset = 0
        while True:
            rows = await session.execute(
                SegmentTable.__table__.select()
                .where(SegmentTable.text.isnot(None))
                .offset(offset)
                .limit(batch_size)
            )
            batch = rows.fetchall()
            if not batch:
                break
            for row in batch:
                passages.append(row.text)
                passage_ids.append(f"segment:{row.id}")
            offset += batch_size

    typer.echo(f"Collected {len(passages)} passages. Building PLAID index...")

    service = RAGatoulleColBERTService(index_path=index_path)
    service.build_index(
        passages=passages,
        passage_ids=passage_ids,
        index_name=index_name,
        max_document_length=chunk_size,
        split_documents=True,
    )
    typer.echo(f"PLAID index written to {index_path / index_name}")


if __name__ == "__main__":
    app()
