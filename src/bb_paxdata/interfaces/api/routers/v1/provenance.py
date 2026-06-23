from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.repositories.provenance_repository import (
    ProvenanceRepository,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter(
    prefix="/provenance",
    tags=["Provenance"],
)


def get_provenance_repository(db: AsyncSession = Depends(get_db)):
    """Dependency injection for ProvenanceRepository."""
    return ProvenanceRepository(db)


@router.get("/{result_id}")
async def get_provenance_graph(
    result_id: str,
    repo=Depends(get_provenance_repository),
):
    """Retrieve the complete provenance graph for a given result ID."""
    graph = await repo.get_by_result_id(result_id)

    if not graph:
        raise HTTPException(
            status_code=404,
            detail=f"Provenance graph not found for result_id: {result_id}",
        )

    return graph.model_dump()


@router.get("/{result_id}/dot")
async def get_provenance_dot(
    result_id: str,
    repo=Depends(get_provenance_repository),
):
    """Retrieve the provenance graph in Graphviz DOT format."""
    graph = await repo.get_by_result_id(result_id)

    if not graph:
        raise HTTPException(
            status_code=404,
            detail=f"Provenance graph not found for result_id: {result_id}",
        )

    return {"result_id": result_id, "format": "dot", "content": graph.to_dot_format()}


@router.get("/{result_id}/mermaid")
async def get_provenance_mermaid(
    result_id: str,
    repo=Depends(get_provenance_repository),
):
    """Retrieve the provenance graph in Mermaid diagram format."""
    graph = await repo.get_by_result_id(result_id)

    if not graph:
        raise HTTPException(
            status_code=404,
            detail=f"Provenance graph not found for result_id: {result_id}",
        )

    return {
        "result_id": result_id,
        "format": "mermaid",
        "content": graph.to_mermaid_format(),
    }


@router.get("/correlation/{correlation_id}")
async def get_provenance_by_correlation(
    correlation_id: str,
    repo=Depends(get_provenance_repository),
):
    """Retrieve all provenance graphs for a given correlation ID."""
    graphs = await repo.get_by_correlation_id(correlation_id)

    if not graphs:
        raise HTTPException(
            status_code=404,
            detail=f"No provenance graphs found for correlation_id: {correlation_id}",
        )

    return [graph.model_dump() for graph in graphs]
