from bb_paxdata.interfaces.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)


def test_global_exception_handler():
    # Dynamically register a test endpoint that throws an unhandled error
    @app.get("/test-error-endpoint")
    def trigger_error():
        raise ValueError("Simulated unexpected database or server crash")

    response = client.get("/test-error-endpoint")
    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Internal Server Error"
    assert "message" in data
