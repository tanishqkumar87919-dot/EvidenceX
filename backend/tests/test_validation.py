import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_validation_missing_text():
    response = client.post("/api/v1/verify/text", json={})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in data["error"]
    assert data["error"]["details"] is not None


def test_validation_text_too_short():
    response = client.post("/api/v1/verify/text", json={"text": "ab"})
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_validation_invalid_url():
    response = client.post("/api/v1/verify/url", json={"url": "not-a-valid-url"})
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_validation_invalid_enum_depth():
    response = client.post(
        "/api/v1/verify/text",
        json={"text": "The moon is made of cheese.", "depth": "ultra-super-deep"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_validation_error_format_structure():
    response = client.post("/api/v1/verify/text", json={"text": ""})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert "code" in error
    assert "message" in error
    assert "request_id" in error
    assert "details" in error
    # No stack trace leak
    assert "traceback" not in response.text.lower()
