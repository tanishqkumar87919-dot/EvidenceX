import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "EvidenceX Backend API"
    assert data["health"] == "/api/v1/health"
    assert "request_id" in data
    assert "X-Request-ID" in response.headers


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "EvidenceX Backend"
    assert "version" in data

    # Verify no secrets or credentials leaked
    body_str = response.text.lower()
    assert "password" not in body_str
    assert "secret" not in body_str
    assert "apikey" not in body_str
    assert "token" not in body_str
    assert "postgresql://" not in body_str
