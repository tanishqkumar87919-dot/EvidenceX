import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_api_v1_routes_exist():
    """Verify that all required v1 endpoints are registered and routed."""
    routes = [
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/system/status"),
        ("POST", "/api/v1/verify/text"),
        ("POST", "/api/v1/verify/url"),
        ("POST", "/api/v1/verify/image"),
        ("POST", "/api/v1/verify/audio"),
        ("POST", "/api/v1/investigations"),
        ("GET", "/api/v1/investigations/test-inv-123"),
        ("GET", "/api/v1/investigations/test-inv-123/status"),
        ("GET", "/api/v1/investigations/test-inv-123/claims"),
        ("GET", "/api/v1/investigations/test-inv-123/evidence"),
        ("GET", "/api/v1/investigations/test-inv-123/timeline"),
        ("POST", "/api/v1/investigations/test-inv-123/copilot"),
        ("GET", "/api/v1/claims/test-claim-456"),
        ("GET", "/api/v1/evidence/test-ev-789"),
        ("GET", "/api/v1/timeline/test-inv-123"),
        ("GET", "/api/v1/analytics/overview"),
        ("POST", "/api/v1/copilot"),
        ("GET", "/api/v1/settings"),
        ("PUT", "/api/v1/settings"),
    ]

    for method, path in routes:
        # None of these routes should return 404 Not Found (route exists)
        if method == "GET":
            response = client.get(path)
        else:
            response = client.post(path, json={})
        assert response.status_code != 404, f"Route {method} {path} was not found (404)"
