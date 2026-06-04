import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

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
