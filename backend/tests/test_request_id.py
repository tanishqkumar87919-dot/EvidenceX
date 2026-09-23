import re
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_generated_request_id():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    req_id = response.headers["X-Request-ID"]
    # Check that it's a valid non-empty string / UUID format
    assert len(req_id) >= 16


def test_propagated_client_request_id():
    custom_id = "test-client-req-99999"
    response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id


def test_request_id_in_error_response():
    custom_id = "err-trace-12345"
    response = client.post(
        "/api/v1/verify/text",
        json={},
        headers={"X-Request-ID": custom_id},
    )
    assert response.status_code == 422
    data = response.json()
    assert response.headers["X-Request-ID"] == custom_id
    assert data["error"]["request_id"] == custom_id


def test_request_id_in_service_not_ready():
    custom_id = "snr-check-777"
    response = client.post(
        "/api/v1/verify/text",
        json={"text": "Water boils at 100 degrees Celsius."},
        headers={"X-Request-ID": custom_id},
    )
    assert response.status_code == 501
    assert response.headers["X-Request-ID"] == custom_id
    data = response.json()
    assert data["request_id"] == custom_id
