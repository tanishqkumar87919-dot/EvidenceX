import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_system_status_endpoint():
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["service"] == "EvidenceX Backend"
    assert "version" in data
    assert "supported_modalities" in data
    assert set(data["supported_modalities"]) == {"TEXT", "IMAGE", "URL", "AUDIO"}
    assert "subsystems" in data
    assert "request_id" in data


def test_system_status_zero_secret_exposure():
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    content = response.text.lower()

    # Strictly verify NO secrets, keys, or database credentials are exposed
    assert "password" not in content
    assert "secret" not in content
    assert "service_role" not in content
    assert "apikey" not in content
    assert "postgresql://" not in content
    assert "supabase_anon_key" not in content
