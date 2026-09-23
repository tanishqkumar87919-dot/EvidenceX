# EvidenceX Backend — Phase 1: FastAPI Foundation & API Contracts

Welcome to the **EvidenceX Backend Engine**.

EvidenceX is a multimodal claim verification and evidence intelligence platform supporting **TEXT**, **IMAGE**, **URL**, and **AUDIO** verification modalities.

> [!IMPORTANT]
> **Implementation Phase Notice**:
> This codebase currently implements **PHASE 1 ONLY**: FastAPI framework foundation, strictly versioned `/api/v1` API contracts, request validation, audio modality upload ingestion guardrails, structured logging with correlation request IDs, and unified error handling.
>
> **Phase 1 does NOT implement actual AI verification**, OCR extraction, Whisper speech-to-text models, claim extraction LLMs, NLI/ML models, or web search evidence retrieval. All verification endpoints return transparent `service_not_ready` structured responses. Zero fabricated claims, transcripts, evidence, or verdicts are returned.

---

## 1. Prerequisites

- **Python**: `3.11+` (tested on Python 3.11 - 3.14)
- **Package Manager**: `pip` (or `uv`)
- **Virtual Environment**: `venv`

---

## 2. Setup & Installation

### Step 1: Create and Activate Virtual Environment
```bash
# Navigate to project root
cd "/Users/tanishqkumar/Desktop/Binary club hackthon "

# Create virtual environment inside backend/ (if not already present)
python3 -m venv backend/.venv

# Activate virtual environment
source backend/.venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### Step 3: Configure Environment Variables
Copy the configuration template:
```bash
cp .env.example .env
```
Key configuration settings for Phase 1:
- `APP_ENV`: `development` or `production`
- `PORT`: `8000` (default)
- `HOST`: `0.0.0.0`
- `CORS_ORIGINS`: Allowed origins (e.g., `http://localhost:3000,http://127.0.0.1:3000`)
- `DEFAULT_MODE`: `LIVE`
- `MAX_AUDIO_SIZE_BYTES`: Max audio size (default `26214400` / 25MB)
- `MAX_IMAGE_SIZE_BYTES`: Max image size (default `10485760` / 10MB)

---

## 3. Running the Server Locally

Start the FastAPI application with Uvicorn:
```bash
backend/.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 4. API Endpoints Directory (Version 1 Prefix: `/api/v1`)

| Method | Endpoint | Phase 1 Status | Description |
| --- | --- | --- | --- |
| `GET` | `/` | Implemented | Root service information, documentation links, and correlation ID |
| `GET` | `/api/v1/health` | Implemented | Lightweight health probe (`{"status": "healthy", "service": "EvidenceX Backend", "version": "1.0.0"}`) |
| `GET` | `/api/v1/system/status` | Implemented | Safe system architecture readiness & modality audit (zero credential leaks) |
| `POST` | `/api/v1/verify/text` | Contract | Text claim intake; validates bounds; returns `service_not_ready` |
| `POST` | `/api/v1/verify/image` | Contract | Image/screenshot intake; validates image MIME/extension/size; returns `service_not_ready` |
| `POST` | `/api/v1/verify/url` | Contract | URL claim intake; validates scheme/host; returns `service_not_ready` |
| `POST` | `/api/v1/verify/audio` | Contract | Audio recording intake; validates audio format/size/non-empty; returns `service_not_ready` |
| `POST` | `/api/v1/investigations` | Contract | Investigation creation contract; returns `service_not_ready` |
| `GET` | `/api/v1/investigations/{id}` | Contract | Investigation detail query; returns `service_not_ready` |
| `GET` | `/api/v1/investigations/{id}/status` | Contract | Live pipeline stage tracker; returns `service_not_ready` |
| `GET` | `/api/v1/investigations/{id}/claims` | Contract | Atomic claims query; returns `service_not_ready` |
| `GET` | `/api/v1/investigations/{id}/evidence` | Contract | Investigation evidence query; returns `service_not_ready` |
| `GET` | `/api/v1/investigations/{id}/timeline` | Contract | Chronological timeline query; returns `service_not_ready` |
| `POST` | `/api/v1/investigations/{id}/copilot` | Contract | Copilot inquiry; returns `service_not_ready` |
| `GET` | `/api/v1/claims/{claim_id}` | Contract | Atomic claim assessment query; returns `service_not_ready` |
| `GET` | `/api/v1/evidence/{evidence_id}` | Contract | Specific evidence citation query; returns `service_not_ready` |
| `GET` | `/api/v1/timeline/{investigation_id}` | Contract | Timeline events query; returns `service_not_ready` |
| `GET` | `/api/v1/analytics/overview` | Contract | Veracity and diversity metrics; returns transparent empty/not-ready |
| `POST` | `/api/v1/copilot` | Contract | Grounded AI copilot inquiry; returns `service_not_ready` |
| `GET` | `/api/v1/settings` | Implemented | User interface preferences (Theme, Language, Depth, Privacy) |
| `PUT` | `/api/v1/settings` | Implemented | Update user interface preferences |

---

## 5. Audio Input Modality Specification

Supported audio formats:
- `audio/mpeg` (`.mp3`)
- `audio/wav`, `audio/x-wav` (`.wav`)
- `audio/mp4`, `audio/m4a` (`.m4a`, `.mp4`)
- `audio/webm` (`.webm`)
- `audio/ogg` (`.ogg`)
- `audio/flac` (`.flac`)

Validation rules:
- Empty uploads (0 bytes) rejected with HTTP 400 (`EMPTY_FILE`).
- Unsupported file formats or extensions rejected with HTTP 415 (`UNSUPPORTED_MEDIA_TYPE`).
- Files exceeding 25 MB rejected with HTTP 413 (`PAYLOAD_TOO_LARGE`).
- Valid uploads return HTTP 501 `SERVICE_NOT_READY` with zero fake transcripts or claims.

---

## 6. Security Guarantees

1. **No Credentials in Logs**: Structured logger strips sensitive headers (`Authorization`, `apikey`) and tokens.
2. **No Stack Traces**: Production error handler catches all unhandled exceptions and formats safe JSON error objects.
3. **No Credential Leaks**: Neither `/health` nor `/system/status` ever exposes database connection strings, passwords, or service-role keys.
4. **Service-Role Boundary**: The Supabase service role key is strictly backend-only.
5. **No Silent Fake Data**: In `LIVE` mode (default), missing pipelines return transparent `service_not_ready` rather than fabricated claims or verdicts.

---

## 7. Running Tests

Run the complete automated test suite:
```bash
PYTHONPATH=. backend/.venv/bin/pytest backend/tests -v
```
