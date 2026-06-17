import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSockets"])


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
    """Listens to Redis events on 'verdict_events' channel and broadcasts them via WebSocket."""
    import asyncio
    import json

    import redis.asyncio as aioredis

    from bb_paxdata.config.settings import get_settings

    settings = get_settings()
    while True:
        try:
            logger.info("Connecting to Redis Pub/Sub...")
            r = aioredis.Redis.from_url(settings.redis_url, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe("verdict_events")
            logger.info("Subscribed to Redis channel 'verdict_events'")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        event_type = payload.get("event_type")
                        data = payload.get("data", {})

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
                    except Exception as parse_ex:
                        logger.error(f"Error parsing Redis message: {parse_ex}")
        except asyncio.CancelledError:
            logger.info("Redis Pub/Sub listener task cancelled")
            break
        except Exception as e:
            logger.error(f"Redis Pub/Sub listener error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
