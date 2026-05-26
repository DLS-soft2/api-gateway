from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthy():
    response = client.get("/healthy")
    assert response.status_code == 200
    assert response.json() == {"status": "Healthy"}


def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "Ready"}


def test_health_endpoints_require_no_auth():
    for path in ["/healthy", "/ready"]:
        response = client.get(path)
        assert response.status_code == 200


def test_unknown_route_without_auth_returns_401():
    response = client.get("/nonexistent")
    assert response.status_code == 401


def test_request_id_header_on_health():
    response = client.get("/healthy")
    assert "x-request-id" in response.headers
