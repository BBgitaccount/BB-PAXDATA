from bb_paxdata.interfaces.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_check():
    """Verify that the health check endpoint returns 200 OK and expected structure."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "version" in data


def test_metrics():
    """Verify that the metrics endpoint returns 200 OK and Prometheus metrics format."""
    response = client.get("/metrics")
    assert response.status_code == 200
    # Common Prometheus default metrics
    assert "process_cpu_seconds_total" in response.text or "# HELP" in response.text
