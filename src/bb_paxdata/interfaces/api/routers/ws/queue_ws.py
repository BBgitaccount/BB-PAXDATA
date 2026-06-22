import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSockets"])

# Centralized registry of Redis pub/sub channels to subscribe to
# This ensures all relevant channels are subscribed on startup and reconnection
REDIS_SUBSCRIBER_CHANNELS = [
    "verdict_events",  # Queue updates and verdict submissions
    "rag_events",  # RAG query completions
    "judge_events",  # Judge verdict renderings
]


class ConnectionManager:
    """Manages active WebSocket connections and handles broadcasting messages."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket client connected. Active connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
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


async def listen_to_redis_events() -> None:
    """Listens to Redis events on all registered channels and broadcasts them via WebSocket.

    This function maintains persistent subscriptions to all channels defined in
    REDIS_SUBSCRIBER_CHANNELS. It automatically re-subscribes to all channels on
    connection loss or Redis restart, ensuring no events are missed.
    """
    import asyncio
    import json

    import redis.asyncio as aioredis

    from bb_paxdata.config.settings import get_settings

    settings = get_settings()
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
