from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.config.settings import get_settings
from bb_paxdata.domain.enums import DatabaseMode
from bb_paxdata.infrastructure.db.discourse_network_table import (
    DiscourseNetworkEdgeTable,
)
from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
from bb_paxdata.infrastructure.db.models import (
    File,
    FormulaValidationLog,
    ReviewerAssignment,
    Segment,
    Sentence,
    SpeakerProfile,
    Word,
)
from bb_paxdata.interfaces.api.dependencies import PermissionChecker, get_db
from bb_paxdata.interfaces.api.schemas import DatabaseStatsResponse

router = APIRouter(prefix="/database", tags=["Database"])


@router.get("/stats", response_model=DatabaseStatsResponse)
async def get_db_stats(
    db: AsyncSession = Depends(get_db),
    # Require at least 'admin' permission to view internal database stats
    _has_permission: bool = Depends(PermissionChecker("admin")),
):
    """Retrieve database mode, byte size, and row counts across all analytical tables."""
    settings = get_settings()

    # 1. Database Size calculation
    size_bytes = 0
    if settings.database_mode == DatabaseMode.SQLITE:
        try:
            if settings.database_path.exists():
                size_bytes = settings.database_path.stat().st_size
        except Exception:
            size_bytes = 0
    elif settings.database_mode == DatabaseMode.POSTGRESQL:
        try:
            res = await db.execute(text("SELECT pg_database_size(current_database())"))
            size_bytes = res.scalar() or 0
        except Exception:
            size_bytes = 0

    # 2. Dynamic Table Row Counts
    tables_map = {
        "files": File,
        "speaker_profiles": SpeakerProfile,
        "segments": Segment,
        "sentences": Sentence,
        "words": Word,
        "discourse_network_edges": DiscourseNetworkEdgeTable,
        "formula_validation_logs": FormulaValidationLog,
        "ai_human_review_queue": HumanReviewQueue,
        "reviewer_assignments": ReviewerAssignment,
    }

    row_counts: dict[str, int] = {}
    status_str = "healthy"

    for table_name, model in tables_map.items():
        try:
            stmt = select(func.count()).select_from(model)
            res = await db.execute(stmt)
            val = res.scalar()
            row_counts[table_name] = val if val is not None else 0
        except Exception:
            row_counts[table_name] = 0
            status_str = "degraded"

    return DatabaseStatsResponse(
        database_mode=settings.database_mode.value,
        size_bytes=size_bytes,
        status=status_str,
        row_counts=row_counts,
    )
