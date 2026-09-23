import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_get_settings():
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert "settings" in data
    assert "theme" in data["settings"]
    assert "language" in data["settings"]
    assert "default_depth" in data["settings"]
    assert "evidence_preference" in data["settings"]
    assert "request_id" in data


def test_update_settings_valid():
    update_payload = {
        "theme": "dark",
        "language": "hi",
        "default_depth": "deep",
        "evidence_preference": "official",
        "analytics_opt_in": False,
        "telemetry_enabled": False,
        "auto_investigate": True,
    }
    response = client.put("/api/v1/settings", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    settings = data["settings"]
    assert settings["theme"] == "dark"
    assert settings["language"] == "hi"
    assert settings["default_depth"] == "deep"
    assert settings["evidence_preference"] == "official"
    assert settings["analytics_opt_in"] is False
    assert settings["auto_investigate"] is True


def test_update_settings_invalid_theme():
    invalid_payload = {
        "theme": "neon-glow-invalid",
        "language": "en",
        "default_depth": "standard",
        "evidence_preference": "balanced",
    }
    response = client.put("/api/v1/settings", json=invalid_payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
