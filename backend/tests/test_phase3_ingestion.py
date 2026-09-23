import io
import math
import os
import struct
import subprocess
import wave
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.database.models import (
    ClaimModel,
    EvidenceModel,
    InputModel,
    InvestigationModel,
    VerificationResultModel,
)
from backend.app.database.session import SessionLocal
from backend.app.main import app

client = TestClient(app)


# ==============================================================================
# Helpers for Test Data Generation
# ==============================================================================

def create_test_image(text: str, fmt: str = "PNG") -> bytes:
    """Generates an image with clearly rendered text for OCR testing."""
    img = Image.new("RGB", (650, 180), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((25, 60), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def create_silent_wav(duration_sec: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Creates a valid WAV file with silence/zeros."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        n_samples = int(duration_sec * sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


def create_speech_wav(statement: str, tmp_path: str = "/tmp/phase3_speech.wav") -> bytes:
    """Generates real speech audio on macOS using say, or falls back to synthetic audio."""
    try:
        cmd = ["/usr/bin/say", statement, "-o", tmp_path, "--data-format=LEI16@16000"]
        res = subprocess.run(cmd, capture_output=True, timeout=10)
        if res.returncode == 0 and os.path.exists(tmp_path):
            with open(tmp_path, "rb") as f:
                return f.read()
    except Exception:
        pass
    # Fallback to audio tone if say is unavailable
    return create_silent_wav(1.0)


# ==============================================================================
# 1. TEXT INGESTION TESTS
# ==============================================================================

def test_unseen_text_claim_ingestion():
    unseen_claim = "The James Webb Space Telescope detected atmospheric carbon dioxide on exoplanet WASP-39 b."
    response = client.post(
        "/api/v1/verify/text",
        json={"text": unseen_claim},
        headers={"X-Request-ID": "test-text-req-001"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["input_type"] == "TEXT"
    assert data["input_mode"] == "LIVE"
    assert data["status"] == "received"
    assert data["request_id"] == "test-text-req-001"
    assert data["extracted_text"] == unseen_claim
    assert data["language"] == "en"
    assert "verdict" not in data
    assert "claims" not in data

    # Verify DB persistence
    db = SessionLocal()
    try:
        inv = db.get(InvestigationModel, data["investigation_id"])
        assert inv is not None
        assert inv.input_type == "TEXT"
        assert inv.input_mode == "LIVE"

        inputs = db.scalars(select(InputModel).where(InputModel.investigation_id == inv.id)).all()
        assert len(inputs) == 1
        assert inputs[0].original_text == unseen_claim
        assert inputs[0].content_hash is not None
    finally:
        db.close()


def test_paragraph_text_ingestion():
    paragraph = (
        "Quantum computing harnesses the phenomena of superposition and entanglement. "
        "Unlike classical bits which represent either 0 or 1, qubits can exist in a linear combination of both states. "
        "This allows quantum algorithms to solve certain mathematical problems exponentially faster."
    )
    response = client.post("/api/v1/verify/text", json={"text": paragraph})
    assert response.status_code == 200
    data = response.json()
    assert data["extracted_text"] == paragraph
    assert data["metadata"]["word_count"] > 25


def test_multiple_factual_statements_preserved():
    multi_statements = (
        "Statement 1: Mount Everest is 8,848 meters high.\n"
        "Statement 2: The Mariana Trench is the deepest oceanic trench.\n"
        "Statement 3: The Amazon is the largest river by discharge volume."
    )
    response = client.post("/api/v1/verify/text", json={"text": multi_statements})
    assert response.status_code == 200
    data = response.json()
    # Preserves entire content without splitting claims in Phase 3
    assert "Statement 1" in data["extracted_text"]
    assert "Statement 2" in data["extracted_text"]
    assert "Statement 3" in data["extracted_text"]


def test_empty_text_rejected():
    response = client.post("/api/v1/verify/text", json={"text": "   "})
    assert response.status_code == 422 or response.status_code == 400
    data = response.json()
    assert "error" in data


def test_oversized_text_rejected():
    huge_text = "A" * 50005
    response = client.post("/api/v1/verify/text", json={"text": huge_text})
    assert response.status_code == 422 or response.status_code == 400


# ==============================================================================
# 2. IMAGE / OCR INGESTION TESTS
# ==============================================================================

def test_real_screenshot_ocr_png():
    img_statement = "The speed of sound in air is approximately 343 meters per second."
    png_bytes = create_test_image(img_statement, fmt="PNG")

    response = client.post(
        "/api/v1/verify/image",
        files={"file": ("physics_fact.png", io.BytesIO(png_bytes), "image/png")},
        data={"depth": "standard", "mode": "LIVE"},
        headers={"X-Request-ID": "test-img-req-002"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["input_type"] == "IMAGE"
    assert data["input_mode"] == "LIVE"
    assert data["request_id"] == "test-img-req-002"
    assert data["language"] in ("en", "UNKNOWN")
    assert "speed" in data["extracted_text"].lower() or "sound" in data["extracted_text"].lower()
    assert data["metadata"]["ocr_confidence"] > 0.0
    assert data["metadata"]["regions_count"] > 0
    assert "verdict" not in data

    # Verify DB persistence
    db = SessionLocal()
    try:
        inv = db.get(InvestigationModel, data["investigation_id"])
        assert inv is not None
        assert inv.input_type == "IMAGE"
        inputs = db.scalars(select(InputModel).where(InputModel.investigation_id == inv.id)).all()
        assert len(inputs) == 1
        assert inputs[0].image_storage_reference is not None
        assert "images/" in inputs[0].image_storage_reference
        assert inputs[0].extracted_text == data["extracted_text"]
    finally:
        db.close()


def test_real_screenshot_ocr_jpeg():
    img_statement = "Oxygen constitutes roughly 21 percent of Earth atmosphere."
    jpg_bytes = create_test_image(img_statement, fmt="JPEG")

    response = client.post(
        "/api/v1/verify/image",
        files={"file": ("atmosphere.jpg", io.BytesIO(jpg_bytes), "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["input_type"] == "IMAGE"
    assert "atmosphere" in data["extracted_text"].lower() or "oxygen" in data["extracted_text"].lower()


def test_corrupted_image_rejected():
    corrupted_bytes = b"\x89PNG\r\n\x1a\n" + b"\xff\x00\x12\x34" * 10
    response = client.post(
        "/api/v1/verify/image",
        files={"file": ("corrupt.png", io.BytesIO(corrupted_bytes), "image/png")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "CORRUPTED_IMAGE"


def test_blank_image_no_text_detected_handling():
    blank = Image.new("RGB", (200, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    blank.save(buf, format="PNG")

    response = client.post(
        "/api/v1/verify/image",
        files={"file": ("blank.png", io.BytesIO(buf.getvalue()), "image/png")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "NO_TEXT_DETECTED_IN_IMAGE"


# ==============================================================================
# 3. URL INGESTION & SSRF PROTECTION TESTS
# ==============================================================================

def test_url_ssrf_blocked_localhost():
    response = client.post("/api/v1/verify/url", json={"url": "http://localhost:8000/api/v1/health"})
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "SSRF_ATTEMPT_DETECTED"


def test_url_ssrf_blocked_loopback_ip():
    response = client.post("/api/v1/verify/url", json={"url": "http://127.0.0.1:8000/secret"})
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "SSRF_ATTEMPT_DETECTED"


def test_url_ssrf_blocked_private_ip():
    response = client.post("/api/v1/verify/url", json={"url": "http://192.168.1.1/admin"})
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "SSRF_ATTEMPT_DETECTED"


def test_url_ssrf_blocked_cloud_metadata():
    response = client.post("/api/v1/verify/url", json={"url": "http://169.254.169.254/latest/meta-data"})
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "SSRF_ATTEMPT_DETECTED"


def test_url_invalid_scheme_rejected():
    response = client.post("/api/v1/verify/url", json={"url": "ftp://files.example.com/test.txt"})
    assert response.status_code == 422 or response.status_code == 400


def test_url_real_public_web_ingestion(monkeypatch):
    """Mocks network fetch to safely test HTML article & metadata parsing."""
    sample_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Renewable Energy Surges Globally</title>
        <meta property="og:title" content="Renewable Energy Surges Globally" />
        <meta property="og:site_name" content="CleanTech News" />
        <meta name="author" content="Dr. Sarah Connor" />
        <meta property="article:published_time" content="2026-03-15T10:00:00Z" />
        <link rel="canonical" href="https://cleantech.org/news/renewable-surge" />
      </head>
      <body>
        <nav><a href="/">Home</a></nav>
        <article>
          <h1>Renewable Energy Surges Globally</h1>
          <p>Global renewable energy generation capacity increased by 50% year-over-year in 2023, driven primarily by solar photovoltaic installations across international markets.</p>
          <p>International energy agencies confirm that solar and wind now account for the vast majority of new power additions worldwide.</p>
        </article>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """

    from backend.app.services.input_processing.url import url_service

    async def mock_fetch(url: str):
        return sample_html, "https://cleantech.org/news/renewable-surge"

    monkeypatch.setattr(url_service, "fetch_url", mock_fetch)

    response = client.post(
        "/api/v1/verify/url",
        json={"url": "https://cleantech.org/news/renewable-surge"},
        headers={"X-Request-ID": "test-url-req-003"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["input_type"] == "URL"
    assert data["input_mode"] == "LIVE"
    assert data["request_id"] == "test-url-req-003"
    assert "solar" in data["extracted_text"].lower()
    assert data["metadata"]["title"] == "Renewable Energy Surges Globally"
    assert data["metadata"]["author"] == "Dr. Sarah Connor"
    assert data["metadata"]["publisher"] == "CleanTech News"
    assert data["metadata"]["canonical_url"] == "https://cleantech.org/news/renewable-surge"
    assert "verdict" not in data

    # Verify DB persistence
    db = SessionLocal()
    try:
        inv = db.get(InvestigationModel, data["investigation_id"])
        assert inv is not None
        assert inv.input_type == "URL"
        inputs = db.scalars(select(InputModel).where(InputModel.investigation_id == inv.id)).all()
        assert len(inputs) == 1
        assert inputs[0].url == "https://cleantech.org/news/renewable-surge"
        assert inputs[0].extracted_text == data["extracted_text"]
    finally:
        db.close()


# ==============================================================================
# 4. AUDIO INGESTION & REAL SPEECH-TO-TEXT TESTS
# ==============================================================================

def test_real_audio_speech_to_text():
    spoken_claim = "The speed of light in a vacuum is 300,000 kilometers per second."
    wav_bytes = create_speech_wav(spoken_claim, tmp_path="/tmp/audio_stt_test.wav")

    response = client.post(
        "/api/v1/verify/audio",
        files={"file": ("speed_of_light.wav", io.BytesIO(wav_bytes), "audio/wav")},
        data={"depth": "standard", "mode": "LIVE"},
        headers={"X-Request-ID": "audio-stt-req-004"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["input_type"] == "AUDIO"
    assert data["input_mode"] == "LIVE"
    assert data["request_id"] == "audio-stt-req-004"
    assert data["status"] == "received"
    assert data["audio_transcript"] is not None
    assert len(data["audio_transcript"]) > 0
    # Whisper real transcription matches factual statement
    assert "speed" in data["audio_transcript"].lower() or "light" in data["audio_transcript"].lower()
    assert data["language"] in ("en", "UNKNOWN")
    assert data["metadata"]["audio_duration"] > 0
    assert data["metadata"]["stt_provider"] == "faster_whisper"
    assert "verdict" not in data

    # Verify DB persistence with Phase 2 audio fields
    db = SessionLocal()
    try:
        inv = db.get(InvestigationModel, data["investigation_id"])
        assert inv is not None
        assert inv.input_type == "AUDIO"
        assert inv.input_mode == "LIVE"

        inputs = db.scalars(select(InputModel).where(InputModel.investigation_id == inv.id)).all()
        assert len(inputs) == 1
        rec = inputs[0]
        assert rec.audio_transcript == data["audio_transcript"]
        assert rec.audio_transcription_status == "COMPLETED"
        assert rec.audio_duration is not None
        assert rec.audio_storage_reference is not None
        assert "audio/" in rec.audio_storage_reference
    finally:
        db.close()


def test_audio_corrupted_file_rejected():
    corrupt_audio = b"\xff\xfb\x90\x44" + b"\xde\xad\xbe\xef" * 10
    response = client.post(
        "/api/v1/verify/audio",
        files={"file": ("corrupt.mp3", io.BytesIO(corrupt_audio), "audio/mpeg")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "CORRUPTED_AUDIO"


def test_audio_transcription_failure_handling():
    """Silent WAV audio contains no recognizable speech, triggering structured failure."""
    silent_wav = create_silent_wav(duration_sec=0.8)
    response = client.post(
        "/api/v1/verify/audio",
        files={"file": ("silent.wav", io.BytesIO(silent_wav), "audio/wav")},
        headers={"X-Request-ID": "silent-req-005"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "transcription_failed"
    assert data["request_id"] == "silent-req-005"
    assert "investigation_id" in data
    assert "transcription could not be completed" in data["message"].lower()


# ==============================================================================
# 5. DATABASE INTEGRITY & ISOLATION TESTS
# ==============================================================================

def test_all_four_modalities_db_persistence():
    db = SessionLocal()
    try:
        invs = db.scalars(select(InvestigationModel)).all()
        persisted_types = {inv.input_type for inv in invs}
        assert "TEXT" in persisted_types
        assert "IMAGE" in persisted_types
        assert "URL" in persisted_types
        assert "AUDIO" in persisted_types
    finally:
        db.close()


def test_zero_fake_claims_or_evidence_persisted():
    """Confirms strict constraint: real claims may be extracted, but ZERO fake evidence or verdicts fabricated."""
    db = SessionLocal()
    try:
        evidence = db.scalars(select(EvidenceModel)).all()
        verdicts = db.scalars(select(VerificationResultModel)).all()

        assert len(evidence) == 0, f"Found {len(evidence)} unexpectedly created evidence!"
        assert len(verdicts) == 0, f"Found {len(verdicts)} unexpectedly created verification results!"
    finally:
        db.close()


def test_safe_references_no_private_paths_exposed():
    """Confirms that internal local filesystem paths (/Users/..., /tmp/...) are never returned."""
    response = client.post(
        "/api/v1/verify/text",
        json={"text": "The boiling point of liquid nitrogen is minus 196 degrees Celsius."},
    )
    body_str = response.text
    assert "/Users/" not in body_str
    assert "/tmp/" not in body_str
    assert "DATABASE_URL" not in body_str
    assert "service_role" not in body_str
