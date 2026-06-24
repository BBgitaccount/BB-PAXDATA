"""Stream metrics and monitoring endpoints."""

from fastapi import APIRouter

from bb_paxdata.application.services.stream_processor import get_stream_processor

router = APIRouter(prefix="/stream", tags=["Stream"])


@router.get("/metrics")
async def get_stream_metrics():
    """Get current stream processor metrics."""
    stream_processor = get_stream_processor()

    backpressure_status = await stream_processor.get_backpressure_status()
    session_metrics = await stream_processor.get_all_session_metrics()

    # Calculate average processing time from session metrics
    total_processing_time = 0
    session_count = 0
    for session_id, metrics in session_metrics.items():
        start_time = metrics.get("start_time")
        items_processed = metrics.get("items_processed", 0)
        if start_time and items_processed > 0:
            import time

            elapsed = time.time() - start_time
            avg_time = elapsed / items_processed
            total_processing_time += avg_time
            session_count += 1

    average_processing_time = (
        total_processing_time / session_count if session_count > 0 else 0
    )

    return {
        **backpressure_status,
        "active_connections": len(
            stream_processor._session_metrics
        ),  # Approximate from active sessions
        "average_processing_time": round(
            average_processing_time * 1000, 2
        ),  # Convert to ms
    }


@router.get("/sessions/{session_id}/metrics")
async def get_session_metrics(session_id: str):
    """Get metrics for a specific session."""
    stream_processor = get_stream_processor()
    metrics = await stream_processor.get_session_metrics(session_id)

    return {
        "session_id": session_id,
        "metrics": metrics,
    }


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear data for a specific session."""
    stream_processor = get_stream_processor()
    await stream_processor.clear_session(session_id)

    return {"message": f"Session {session_id} cleared"}
