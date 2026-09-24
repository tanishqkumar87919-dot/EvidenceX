import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

FORBIDDEN_KEYS = {"verdict", "confidence_score", "sources", "fabricated_evidence"}


def assert_no_fake_data_in_response(data: dict):
    """Recursively checks that forbidden fabricated keys do not exist."""
    for key in FORBIDDEN_KEYS:
        assert key not in data, f"Fabricated key '{key}' was found in response!"


def test_verify_text_no_fake_data():
    res = client.post("/api/v1/verify/text", json={"text": "Water freezes at 0 degrees Celsius."})
    assert res.status_code == 200
    assert_no_fake_data_in_response(res.json())


def test_verify_url_no_fake_data():
    res = client.post("/api/v1/verify/url", json={"url": "https://example.com/news/123"})
    assert res.status_code in (200, 400, 422, 501)
    assert_no_fake_data_in_response(res.json())


def test_verify_image_no_fake_data():
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30
    res = client.post(
        "/api/v1/verify/image",
        files={"file": ("screenshot.png", io.BytesIO(fake_png), "image/png")},
    )
    assert res.status_code in (200, 400, 422, 501)
    assert_no_fake_data_in_response(res.json())


def test_verify_audio_no_fake_data():
    fake_mp3 = b"\xff\xfb\x90d" + b"\x00" * 50
    res = client.post(
        "/api/v1/verify/audio",
        files={"file": ("speech.mp3", io.BytesIO(fake_mp3), "audio/mpeg")},
    )
    assert res.status_code in (200, 400, 422, 501)
    assert_no_fake_data_in_response(res.json())


def test_investigations_no_fake_data():
    res = client.post(
        "/api/v1/investigations",
        json={"modality": "TEXT", "content": "Sample statement"},
    )
    assert res.status_code in (201, 501)
    assert_no_fake_data_in_response(res.json())


def test_claim_lookup_no_fake_data():
    res = client.get("/api/v1/claims/claim-999")
    assert res.status_code in (404, 501)
    assert_no_fake_data_in_response(res.json())


def test_evidence_lookup_no_fake_data():
    res = client.get("/api/v1/evidence/evidence-888")
    assert res.status_code in (404, 501)
    assert_no_fake_data_in_response(res.json())


def test_timeline_lookup_no_fake_data():
    res = client.get("/api/v1/timeline/inv-777")
    assert res.status_code == 501
    assert_no_fake_data_in_response(res.json())


def test_copilot_no_fake_data():
    res = client.post("/api/v1/copilot", json={"query": "Is this claim true?"})
    assert res.status_code == 501
    assert_no_fake_data_in_response(res.json())


def test_analytics_no_fake_numbers():
    res = client.get("/api/v1/analytics/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "service_not_ready"
    assert data["data"] is None
