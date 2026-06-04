"""Export BB-PAXDATA analysis results and graph topology to Parquet."""

import io
import json
import logging
import os
from datetime import UTC, datetime

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from bb_paxdata.infrastructure.db.models import AISentenceAnalysis, Sentence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Schemas ──────────────────────────────────────────────────────────────────
SCHEMA_SENTENCES = pa.schema(
    [
        pa.field("sent_id", pa.string()),
        pa.field("file_id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("speaker_name", pa.string()),
        pa.field("country", pa.string()),
        pa.field("ai_risk_score", pa.int16(), nullable=True),
        pa.field("ai_duygu_skoru", pa.float32(), nullable=True),
        pa.field("ai_diplomatik_ton", pa.string(), nullable=True),
        pa.field("ai_birincil_konu", pa.string(), nullable=True),
        pa.field("ai_manipulasyon_skor", pa.float32(), nullable=True),
        pa.field("coherence_score", pa.float32(), nullable=True),
        pa.field("created_at", pa.timestamp("ms", tz="UTC"), nullable=True),
    ]
)

SCHEMA_GRAPH = pa.schema(
    [
        pa.field("snapshot_date", pa.timestamp("ms", tz="UTC")),
        pa.field("node_id", pa.string()),
        pa.field("node_label", pa.string()),
        pa.field("community_id", pa.int64()),
        pa.field("community_name", pa.string()),
        pa.field("cohesion", pa.float32()),
        pa.field("degree", pa.int32()),
        pa.field("betweenness", pa.float32()),
        pa.field("is_inferred", pa.bool_()),
    ]
)


async def export_to_parquet(
    db: AsyncSession,
    s3_bucket: str,
    s3_prefix: str = "paxdata-archive",
    aws_endpoint_url: str | None = None,
) -> str:
    """Exports sentences and graph topology snapshots to S3/MinIO.

    Returns the keys of the exported resources.
    """
    today = datetime.now(UTC)
    prefix = f"{s3_prefix}/{today.year}/{today.month:02d}/{today.day:02d}"

    # 1. Export Sentences
    stmt = (
        select(
            AISentenceAnalysis.sent_id,
            AISentenceAnalysis.file_id,
            Sentence.text,
            Sentence.speaker_name,
            Sentence.country,
            AISentenceAnalysis.ai_risk_score,
            AISentenceAnalysis.sentiment_score.label("ai_duygu_skoru"),
            AISentenceAnalysis.diplomatic_tone.label("ai_diplomatik_ton"),
            AISentenceAnalysis.primary_topic.label("ai_birincil_konu"),
            AISentenceAnalysis.manipulation_score.label("ai_manipulasyon_skor"),
            AISentenceAnalysis.coherence_score,
            AISentenceAnalysis.created_at,
        )
        .join(Sentence, Sentence.sent_id == AISentenceAnalysis.sent_id)
        .order_by(AISentenceAnalysis.created_at.asc())
    )

    res = await db.execute(stmt)
    rows = res.fetchall()

    s3_kwargs = {}
    if aws_endpoint_url:
        s3_kwargs["endpoint_url"] = aws_endpoint_url
        s3_kwargs["aws_access_key_id"] = "paxdata_access_key"
        s3_kwargs["aws_secret_access_key"] = "paxdata_secret_key"

    s3 = boto3.client("s3", **s3_kwargs)

    sentences_key = f"{prefix}/sentences.parquet"
    if rows:
        df_sent = pd.DataFrame(
            rows,
            columns=[
                "sent_id",
                "file_id",
                "text",
                "speaker_name",
                "country",
                "ai_risk_score",
                "ai_duygu_skoru",
                "ai_diplomatik_ton",
                "ai_birincil_konu",
                "ai_manipulasyon_skor",
                "coherence_score",
                "created_at",
            ],
        )
        df_sent["created_at"] = pd.to_datetime(df_sent["created_at"], utc=True)
        table_sent = pa.Table.from_pandas(df_sent, schema=SCHEMA_SENTENCES, safe=False)
        buf_sent = io.BytesIO()
        pq.write_table(table_sent, buf_sent, compression="snappy")
        buf_sent.seek(0)
        s3.upload_fileobj(buf_sent, s3_bucket, sentences_key)
        logger.info(f"Exported {len(rows)} sentences to {sentences_key}")
    else:
        logger.warning("No sentence rows found to export.")

    # 2. Export Graph Snapshot
    graph_key = f"{prefix}/graph_topology.parquet"
    graph_json_path = "graphify-out/graph.json"
    if os.path.exists(graph_json_path):
        try:
            with open(graph_json_path, encoding="utf-8") as f:
                graph_data = json.load(f)

            nodes = graph_data.get("nodes", [])
            links = graph_data.get("links", [])

            # Compute degrees
            degrees: dict[str, int] = {}
            for link in links:
                src = link.get("source")
                tgt = link.get("target")
                if src:
                    degrees[src] = degrees.get(src, 0) + 1
                if tgt:
                    degrees[tgt] = degrees.get(tgt, 0) + 1

            # Compute is_inferred per node
            node_inferred: dict[str, bool] = {}
            for link in links:
                if link.get("confidence") == "INFERRED":
                    src = link.get("source")
                    tgt = link.get("target")
                    if src:
                        node_inferred[src] = True
                    if tgt:
                        node_inferred[tgt] = True

            graph_rows = []
            for node in nodes:
                node_id = node.get("id")
                comm_id = node.get("community", 0)
                graph_rows.append(
                    {
                        "snapshot_date": today,
                        "node_id": node_id,
                        "node_label": node.get("label", ""),
                        "community_id": int(comm_id) if comm_id is not None else 0,
                        "community_name": f"Community {comm_id}",
                        "cohesion": 1.0,
                        "degree": degrees.get(node_id, 0),
                        "betweenness": 0.0,
                        "is_inferred": node_inferred.get(node_id, False),
                    }
                )

            if graph_rows:
                df_graph = pd.DataFrame(graph_rows)
                table_graph = pa.Table.from_pandas(
                    df_graph, schema=SCHEMA_GRAPH, safe=False
                )
                buf_graph = io.BytesIO()
                pq.write_table(table_graph, buf_graph, compression="snappy")
                buf_graph.seek(0)
                s3.upload_fileobj(buf_graph, s3_bucket, graph_key)
                logger.info(f"Exported {len(graph_rows)} graph nodes to {graph_key}")
        except Exception as e:
            logger.error(f"Failed to export graph snapshot: {e}")
    else:
        logger.warning("graphify-out/graph.json not found. Skipping graph export.")

    return sentences_key
