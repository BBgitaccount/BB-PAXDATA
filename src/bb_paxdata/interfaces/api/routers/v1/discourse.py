from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.discourse_network_table import (
    DiscourseNetworkEdgeTable,
)
from bb_paxdata.infrastructure.db.models import Speaker
from bb_paxdata.interfaces.api.dependencies import PermissionChecker, get_db
from bb_paxdata.interfaces.api.schemas import (
    DiscourseEdge,
    DiscourseNetworkResponse,
    DiscourseNode,
)

router = APIRouter(prefix="/discourse", tags=["Discourse"])


@router.get("/sessions", response_model=list[str])
async def get_discourse_sessions(
    db: AsyncSession = Depends(get_db),
    _has_permission: bool = Depends(PermissionChecker("view")),
):
    """Retrieve all unique discourse network analysis session IDs."""
    stmt = select(DiscourseNetworkEdgeTable.session_id).distinct()
    res = await db.execute(stmt)
    return sorted(list(res.scalars().all()))


@router.get("", response_model=DiscourseNetworkResponse)
async def get_discourse_network(
    session_id: str | None = Query(
        None, max_length=200, description="Filter edges by session/run ID"
    ),
    min_weight: float = Query(
        0.0, ge=0.0, le=1.0, description="Minimum edge weight threshold"
    ),
    db: AsyncSession = Depends(get_db),
    # Require at least 'view' permission to inspect discourse network
    _has_permission: bool = Depends(PermissionChecker("view")),
):
    """Retrieve discourse network analysis actor-concept bipartite graph."""
    if not session_id:
        # Find the latest session_id in the table
        latest_stmt = (
            select(DiscourseNetworkEdgeTable.session_id)
            .order_by(DiscourseNetworkEdgeTable.id.desc())
            .limit(1)
        )
        latest_res = await db.execute(latest_stmt)
        session_id = latest_res.scalar_one_or_none()

    if not session_id:
        # If no edges exist in database, return empty response
        return DiscourseNetworkResponse(nodes=[], edges=[])

    stmt = select(DiscourseNetworkEdgeTable).where(
        DiscourseNetworkEdgeTable.session_id == session_id,
        DiscourseNetworkEdgeTable.weight >= min_weight,
    )
    res = await db.execute(stmt)
    edges_rows = res.scalars().all()

    # Collect unique actor_ids
    actor_ids = set(r.actor_id for r in edges_rows)

    # Fetch speaker names for all actor_ids
    speaker_names = {}
    if actor_ids:
        speaker_stmt = select(Speaker.speaker_id, Speaker.canonical_name).where(
            Speaker.speaker_id.in_(actor_ids)
        )
        speaker_res = await db.execute(speaker_stmt)
        for row in speaker_res:
            speaker_names[row.speaker_id] = row.canonical_name

    nodes_map = {}
    edges_list = []

    for r in edges_rows:
        # Actor node - use speaker canonical_name as label, fallback to actor_id
        if r.actor_id not in nodes_map:
            actor_label = speaker_names.get(r.actor_id, r.actor_id)
            nodes_map[r.actor_id] = DiscourseNode(
                id=r.actor_id, label=actor_label, type="actor"
            )
        # Concept node
        if r.concept_id not in nodes_map:
            nodes_map[r.concept_id] = DiscourseNode(
                id=r.concept_id,
                label=r.concept_id.replace("_", " ").title(),
                type="concept",
            )
        # Edge
        edges_list.append(
            DiscourseEdge(
                source=r.actor_id,
                target=r.concept_id,
                weight=float(r.weight),
                tf=float(r.tf),
                idf=float(r.idf),
            )
        )

    return DiscourseNetworkResponse(nodes=list(nodes_map.values()), edges=edges_list)
