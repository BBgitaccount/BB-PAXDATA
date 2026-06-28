import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from bb_paxdata.application.services.stream_processor import (
    Priority,
    StreamProcessor,
    get_stream_processor,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSockets"])

# Centralized registry of Redis pub/sub channels to subscribe to
# This ensures all relevant channels are subscribed on startup and reconnection
REDIS_SUBSCRIBER_CHANNELS = [
    "verdict_events",  # Queue updates and verdict submissions
    "rag_events",  # RAG query completions
    "judge_events",  # Judge verdict renderings
    "analysis_events",  # Analysis streaming results
    "notification_events",  # Global notifications
    "build_events",  # Ingestion build progress events
]


class ConnectionManager:
    """Manages active WebSocket connections and handles broadcasting messages."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        # Session-specific connections for analysis streaming
        self.session_connections: dict[str, list[WebSocket]] = {}
        # User-specific connections for notifications
        self.user_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket client connected. Active connections: {len(self.active_connections)}"
        )

    async def connect_session(self, websocket: WebSocket, session_id: str) -> None:
        """Connect a WebSocket to a specific analysis session."""
        await websocket.accept()
        if session_id not in self.session_connections:
            self.session_connections[session_id] = []
        self.session_connections[session_id].append(websocket)
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket client connected to session {session_id}. "
            f"Session connections: {len(self.session_connections[session_id])}, "
            f"Total active: {len(self.active_connections)}"
        )

    async def connect_user(self, websocket: WebSocket, user_id: str) -> None:
        """Connect a WebSocket to a specific user for notifications."""
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket client connected for user {user_id}. "
            f"User connections: {len(self.user_connections[user_id])}, "
            f"Total active: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        # Remove from session connections
        for session_id, connections in list(self.session_connections.items()):
            if websocket in connections:
                connections.remove(websocket)
                if not connections:
                    del self.session_connections[session_id]
        # Remove from user connections
        for user_id, connections in list(self.user_connections.items()):
            if websocket in connections:
                connections.remove(websocket)
                if not connections:
                    del self.user_connections[user_id]
        logger.info(
            f"WebSocket client disconnected. Active connections: {len(self.active_connections)}"
        )

    async def broadcast(self, message: dict[str, object]) -> None:
        """Send JSON payload to all active connections."""
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(
                    f"Failed to send WS message to a client, disconnecting: {e}"
                )
                self.disconnect(connection)

    async def send_to_session(
        self, session_id: str, message: dict[str, object]
    ) -> None:
        """Send JSON payload to all connections in a specific session."""
        if session_id not in self.session_connections:
            return

        for connection in list(self.session_connections[session_id]):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(
                    f"Failed to send WS message to session {session_id}, disconnecting: {e}"
                )
                self.disconnect(connection)

    async def send_to_user(self, user_id: str, message: dict[str, object]) -> None:
        """Send JSON payload to all connections for a specific user."""
        if user_id not in self.user_connections:
            return

        for connection in list(self.user_connections[user_id]):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(
                    f"Failed to send WS message to user {user_id}, disconnecting: {e}"
                )
                self.disconnect(connection)


# Global manager instance for routing triggers
manager = ConnectionManager()


@router.websocket("/queue")
async def websocket_queue_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint serving live queue changes and notifications."""
    await manager.connect(websocket)
    try:
        # Keep connection open and respond to client pings/messages if any
        while True:
            data = await websocket.receive_text()
            # Parse echo or custom client triggers if needed
            payload = json.loads(data)
            await websocket.send_json({"status": "echo", "received": payload})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.websocket("/build")
async def websocket_build_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time pipeline build progress monitoring.

    Clients connect here and receive 'IngestionProgress' broadcast payloads
    while a build is running.  A heartbeat ping/pong is supported to keep
    reverse-proxy connections alive.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Await client messages (ping / any keep-alive text)
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                if payload.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass  # Non-JSON keep-alive bytes are fine
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Build WebSocket error: {e}")
        manager.disconnect(websocket)


@router.websocket("/analysis/{session_id}")
async def websocket_analysis_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for streaming analysis results for a specific session.

    Supports:
    - Priority-based result streaming (risk > sentiment > topic)
    - Heartbeat/ping-pong for connection management
    - Stream control (pause/resume via client messages)
    - Partial aggregation of results
    """
    stream_processor = get_stream_processor()
    await manager.connect_session(websocket, session_id)

    # Stream control state
    asyncio.get_event_loop().time()

    try:
        # Start background task to process stream queue for this session
        queue_task = asyncio.create_task(
            _process_analysis_queue(websocket, session_id, stream_processor)
        )

        while True:
            # Receive client messages (control commands, heartbeat)
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)

                # Handle heartbeat
                if payload.get("type") == "ping":
                    asyncio.get_event_loop().time()
                    await websocket.send_json({"type": "pong"})

                # Handle stream control
                elif payload.get("type") == "pause":
                    await websocket.send_json({"type": "stream_paused"})

                elif payload.get("type") == "resume":
                    await websocket.send_json({"type": "stream_resumed"})

                elif payload.get("type") == "rewind":
                    # Send last N aggregated results
                    count = payload.get("count", 5)
                    aggregated = await stream_processor.get_aggregated_results(
                        session_id, flush=False
                    )
                    last_results = (
                        aggregated[-count:] if len(aggregated) > count else aggregated
                    )
                    await websocket.send_json(
                        {
                            "type": "rewind_results",
                            "results": last_results,
                        }
                    )

            except json.JSONDecodeError:
                # Non-JSON keep-alive bytes are fine
                pass
            except Exception as e:
                logger.warning(f"Error processing client message: {e}")

    except WebSocketDisconnect:
        logger.info(f"Analysis WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"Analysis WebSocket error for session {session_id}: {e}")
    finally:
        queue_task.cancel()
        try:
            await queue_task
        except asyncio.CancelledError:
            pass
        manager.disconnect(websocket)
        # Clean up session data
        await stream_processor.clear_session(session_id)


async def _process_analysis_queue(
    websocket: WebSocket,
    session_id: str,
    stream_processor: StreamProcessor,
) -> None:
    """Background task to process and send analysis results from the queue."""
    while True:
        try:
            item = await stream_processor.dequeue()
            if item is None:
                await asyncio.sleep(0.1)
                continue

            # Only send items for this session
            if item.session_id != session_id:
                continue

            # Add to aggregation buffer
            await stream_processor.add_to_aggregation_buffer(session_id, item.data)

            # Send to client
            await websocket.send_json(
                {
                    "type": "analysis_result",
                    "priority": item.priority,
                    "item_id": item.item_id,
                    "data": item.data,
                }
            )

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error processing analysis queue: {e}")
            await asyncio.sleep(0.5)


@router.websocket("/notifications")
async def websocket_notifications_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for global notification streaming.

    Broadcasts system-wide notifications including:
    - Queue updates
    - System alerts
    - Worker status changes
    """
    await manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "message": "Notification stream connected",
            }
        )

        while True:
            # Receive client messages (heartbeat)
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                if payload.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass  # Non-JSON keep-alive bytes are fine

    except WebSocketDisconnect:
        logger.info("Notification WebSocket disconnected")
    except Exception as e:
        logger.error(f"Notification WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


@router.websocket("/notifications/{user_id}")
async def websocket_user_notifications_endpoint(
    websocket: WebSocket, user_id: str
) -> None:
    """WebSocket endpoint for user-specific notification streaming.

    Provides real-time notifications for a specific user including:
    - Export job completions
    - Analysis completions
    - Personal alerts
    """
    await manager.connect_user(websocket, user_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "message": f"User notification stream connected for {user_id}",
                "user_id": user_id,
            }
        )

        while True:
            # Receive client messages (heartbeat)
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                if payload.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass  # Non-JSON keep-alive bytes are fine

    except WebSocketDisconnect:
        logger.info(f"User notification WebSocket disconnected for {user_id}")
    except Exception as e:
        logger.error(f"User notification WebSocket error for {user_id}: {e}")
    finally:
        manager.disconnect(websocket)


async def listen_to_redis_events() -> None:
    """Listens to Redis events on all registered channels and broadcasts them via WebSocket.

    This function maintains persistent subscriptions to all channels defined in
    REDIS_SUBSCRIBER_CHANNELS. It automatically re-subscribes to all channels on
    connection loss or Redis restart, ensuring no events are missed.

    Supports multiple workers by using pattern-based channel subscriptions.
    """
    import json

    import redis.asyncio as aioredis

    from bb_paxdata.config.settings import get_settings

    settings = get_settings()
    stream_processor = get_stream_processor()
    retry_delay = 1  # Initial retry delay in seconds
    max_retry_delay = 30  # Maximum retry delay

    while True:
        try:
            logger.info(
                "Connecting to Redis Pub/Sub...",
                channels=REDIS_SUBSCRIBER_CHANNELS,
            )
            r = aioredis.Redis.from_url(settings.redis_url, decode_responses=True)
            pubsub = r.pubsub()

            # Subscribe to all registered channels
            await pubsub.subscribe(*REDIS_SUBSCRIBER_CHANNELS)
            logger.info(
                "Subscribed to Redis channels",
                channels=REDIS_SUBSCRIBER_CHANNELS,
            )

            # Reset retry delay on successful connection
            retry_delay = 1

            async for message in pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    try:
                        payload = json.loads(message["data"])
                        event_type = payload.get("event_type")
                        data = payload.get("data", {})

                        # Handle verdict_events channel
                        if channel == "verdict_events":
                            if event_type == "new_flagged_item":
                                msg = {"event": "new_flagged_item", **data}
                                await manager.broadcast(msg)
                            elif event_type == "verdict_submitted":
                                msg = {
                                    "event": "queue_updated",
                                    "log_id": data.get("log_id"),
                                    "verdict": data.get("verdict"),
                                    "reviewer_id": data.get("reviewer_id"),
                                }
                                await manager.broadcast(msg)
                        # Handle rag_events channel
                        elif channel == "rag_events":
                            msg = {"event": "rag_query_completed", "data": payload}
                            await manager.broadcast(msg)
                        # Handle judge_events channel
                        elif channel == "judge_events":
                            msg = {"event": "judge_verdict_rendered", "data": payload}
                            await manager.broadcast(msg)
                        # Handle analysis_events channel - route to StreamProcessor
                        elif channel == "analysis_events":
                            session_id = data.get("session_id")
                            if session_id:
                                # Determine priority based on event type
                                priority = Priority.GENERAL
                                if event_type == "risk_detected":
                                    priority = Priority.RISK
                                elif event_type == "sentiment_analyzed":
                                    priority = Priority.SENTIMENT
                                elif event_type == "topic_identified":
                                    priority = Priority.TOPIC

                                # Enqueue for streaming
                                await stream_processor.enqueue(
                                    session_id=session_id,
                                    data=data,
                                    priority=priority,
                                    item_id=data.get("item_id"),
                                )

                                # Also broadcast to session connections
                                await manager.send_to_session(
                                    session_id,
                                    {
                                        "type": "analysis_update",
                                        "event_type": event_type,
                                        "data": data,
                                    },
                                )
                        # Handle notification_events channel
                        elif channel == "notification_events":
                            msg = {"event": "notification", "data": payload}
                            await manager.broadcast(msg)
                        # Handle build_events channel
                        elif channel == "build_events":
                            # The frontend expects: { "type": event_type (IngestionProgress), "data": data }
                            msg = {"type": event_type, "data": data}
                            await manager.broadcast(msg)
                    except Exception as parse_ex:
                        logger.error(
                            "Error parsing Redis message",
                            channel=channel,
                            error=str(parse_ex),
                        )
        except asyncio.CancelledError:
            logger.info("Redis Pub/Sub listener task cancelled")
            break
        except Exception as e:
            logger.error(
                "Redis Pub/Sub listener error",
                error=str(e),
                retry_delay=retry_delay,
            )
            await asyncio.sleep(retry_delay)
            # Exponential backoff with jitter
            retry_delay = min(retry_delay * 2, max_retry_delay)
