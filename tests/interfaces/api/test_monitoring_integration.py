import pytest
from fastapi.testclient import TestClient

from bb_paxdata.infrastructure.auth.jwt_auth import create_jwt
from bb_paxdata.infrastructure.db.models import ReviewerAssignment
from bb_paxdata.interfaces.api.main import app

client = TestClient(app)


@pytest.fixture
def auth_headers():
    """Returns authorization headers for an admin reviewer."""
    token = create_jwt("admin@paxdata.local", roles=["admin"])
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_metrics_endpoint() -> None:
    """Verify that the Prometheus /metrics endpoint is exposed and returns valid format."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    # Prometheus format assertions
    assert "ai_backend_latency_seconds" in response.text or "# HELP" in response.text


@pytest.mark.asyncio
async def test_database_stats_endpoint(test_db_session, auth_headers) -> None:
    """Verify that the /api/v1/database/stats endpoint returns status details when authorized."""
    # Seed admin assignment to pass RBAC
    assignment = ReviewerAssignment(
        reviewer_id="admin@paxdata.local",
        scope_type="global",
        scope_value="global",
        permission_level="admin",
        is_active=True,
        max_daily_reviews=100,
    )
    test_db_session.add(assignment)
    await test_db_session.commit()

    response = client.get("/api/v1/database/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "database_mode" in data
    assert "size_bytes" in data
    assert "status" in data
    assert "row_counts" in data


@pytest.mark.asyncio
async def test_database_stats_forbidden_unauthorized() -> None:
    """Verify /api/v1/database/stats is rejected with 401/403 without authorization."""
    response = client.get("/api/v1/database/stats")
    assert response.status_code in (401, 403)


def test_websocket_build_ping_pong() -> None:
    """Test that connecting to the /api/ws/build WebSocket and sending ping returns a pong."""
    with client.websocket_connect("/api/ws/build") as websocket:
        websocket.send_json({"type": "ping"})
        response = websocket.receive_json()
        assert response == {"type": "pong"}


def test_websocket_queue_echo() -> None:
    """Test that connecting to the /api/ws/queue WebSocket and sending payloads echoes them back."""
    with client.websocket_connect("/api/ws/queue") as websocket:
        payload = {"test": "data"}
        websocket.send_json(payload)
        response = websocket.receive_json()
        assert response["status"] == "echo"
        assert response["received"] == payload
