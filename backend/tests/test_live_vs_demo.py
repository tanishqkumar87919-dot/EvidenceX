import pytest
from fastapi.testclient import TestClient
from backend.app.core.config import settings
from backend.app.main import app

client = TestClient(app)


def test_default_mode_is_live():
    assert settings.DEFAULT_MODE == "LIVE"


def test_live_mode_default_no_silent_demo_fallback():
    response = client.post(
        "/api/v1/verify/text",
        json={"text": "Global renewable capacity surged by 50% in 2023."},
    )
    assert response.status_code in (200, 501)
    data = response.json()
    assert data.get("input_mode") == "LIVE"

    # Strictly verify NO fake claims, transcripts, evidence, or verdicts are present
    assert "verdict" not in data
    assert "evidence" not in data
    assert "confidence" not in data
    assert "sources" not in data


def test_explicit_live_mode_behavior():
    response = client.post(
        "/api/v1/verify/text",
        json={
            "text": "The central bank lowered benchmark interest rates by 25 basis points.",
            "mode": "LIVE",
        },
    )
    assert response.status_code in (200, 501)
    data = response.json()
    assert data.get("input_mode") == "LIVE"
    assert "verdict" not in data


def test_explicit_demo_mode_does_not_fabricate_unimplemented_pipeline():
    response = client.post(
        "/api/v1/verify/text",
        json={
            "text": "The Eiffel Tower was constructed in Paris, France.",
            "mode": "DEMO",
        },
    )
    assert response.status_code in (200, 501)
    data = response.json()
    assert data.get("input_mode") == "DEMO"
    assert "claims" not in data
    assert "verdict" not in data
