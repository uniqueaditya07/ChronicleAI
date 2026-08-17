from fastapi.testclient import TestClient


def test_root_discovery_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "ChronicleAI API"
    assert data["version"] == "0.1.0"
    assert data["status"] == "operational"
    assert data["health"] == "/api/v1/health"


def test_health_check_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "ChronicleAI API"
    assert data["version"] == "0.1.0"
    assert data["database_connected"] is True
    assert "timestamp" in data
