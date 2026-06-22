"""Celery tasks for graph and community management."""

import structlog

from bb_paxdata.infrastructure.tasks.celery_app import get_celery_app

app = get_celery_app()

logger = structlog.get_logger(__name__)


@app.task(
    name="bb_paxdata.infrastructure.tasks.graph_tasks.reindex_communities",
    queue="graph_io",
)
def reindex_communities() -> str:
    """Full reindex of community metadata into Meilisearch."""
    # Stub: Will be integrated once Meilisearch is active
    return "reindex_complete"


@app.task(
    name="bb_paxdata.infrastructure.tasks.graph_tasks.export_graph_snapshot",
    queue="graph_io",
)
def export_graph_snapshot() -> str:
    """Export graph topology to Parquet for data lake."""
    # Stub: Will be integrated once Parquet data lake exporter is active
    return "graph_export_complete"
