import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_cors_allowed_origin():
    origin = "http://localhost:3000"
    response = client.get(
        "/api/v1/health",
        headers={"Origin": origin},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_preflight_options():
    origin = "http://localhost:3000"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,Authorization,X-Request-ID",
    }
    response = client.options("/api/v1/verify/text", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_cors_disallowed_origin():
    disallowed = "http://malicious-external-site.evil"
    response = client.get(
        "/api/v1/health",
        headers={"Origin": disallowed},
    )
    # Origin should not be allowed
    assert response.headers.get("access-control-allow-origin") != disallowed
