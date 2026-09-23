import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_valid_wav_audio_upload():
    # Valid RIFF WAV header bytes (44 bytes standard header)
    wav_header = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    file_payload = ("test_speech.wav", io.BytesIO(wav_header), "audio/wav")

    response = client.post(
        "/api/v1/verify/audio",
        files={"file": file_payload},
        data={"depth": "standard", "mode": "LIVE"},
    )
    # Status should be 501 (Service Not Ready in Phase 1)
    assert response.status_code == 501
    data = response.json()
    assert data["status"] == "service_not_ready"
    assert "Whisper" in data["message"] or "pipeline" in data["message"].lower()

    # CRITICAL: Verify NO fake transcripts or claims are returned
    assert "transcript" not in data
    assert "claims" not in data
    assert "verdict" not in data


def test_valid_mp3_audio_upload():
    # Mock MP3 content
    mp3_bytes = b"\xff\xfb\x90d" + b"\x00" * 100
    file_payload = ("sample_recording.mp3", io.BytesIO(mp3_bytes), "audio/mpeg")

    response = client.post(
        "/api/v1/verify/audio",
        files={"file": file_payload},
        data={"mode": "LIVE"},
    )
    assert response.status_code == 501
    data = response.json()
    assert data["status"] == "service_not_ready"


def test_empty_audio_upload_rejected():
    empty_payload = ("empty.wav", io.BytesIO(b""), "audio/wav")

    response = client.post(
        "/api/v1/verify/audio",
        files={"file": empty_payload},
    )
    # Empty file should be rejected with 400 Bad Request
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] in ("EMPTY_FILE", "BAD_REQUEST")
    assert "empty" in data["error"]["message"].lower()


def test_unsupported_audio_format_rejected():
    text_payload = ("document.txt", io.BytesIO(b"This is a text file, not audio."), "text/plain")

    response = client.post(
        "/api/v1/verify/audio",
        files={"file": text_payload},
    )
    # Unsupported media type should be rejected with 415
    assert response.status_code == 415
    data = response.json()
    assert data["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert "not supported" in data["error"]["message"].lower()


def test_unsupported_extension_with_audio_mime():
    fake_payload = ("malicious.exe", io.BytesIO(b"\x00" * 50), "audio/wav")

    response = client.post(
        "/api/v1/verify/audio",
        files={"file": fake_payload},
    )
    assert response.status_code == 415
    data = response.json()
    assert data["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_oversized_audio_upload_rejected(monkeypatch):
    from backend.app.core.config import settings

    # Temporarily set audio limit to 50 bytes for unit testing
    monkeypatch.setattr(settings, "MAX_AUDIO_SIZE_BYTES", 50)

    large_bytes = b"0" * 100
    file_payload = ("too_large.wav", io.BytesIO(large_bytes), "audio/wav")

    response = client.post(
        "/api/v1/verify/audio",
        files={"file": file_payload},
    )
    assert response.status_code == 413
    data = response.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
