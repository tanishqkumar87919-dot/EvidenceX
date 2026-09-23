# EvidenceX Backend — Phase 3: Real Multimodal Input Ingestion

Welcome to the **EvidenceX Backend Engine**.

EvidenceX is an AI-powered multimodal claim verification and evidence intelligence platform supporting **TEXT**, **IMAGE**, **URL**, and **AUDIO** verification modalities.

> [!IMPORTANT]
> **Implementation Phase Notice**:
> This codebase implements **PHASES 1, 2, & 3**:
> - **Phase 1**: FastAPI foundation, strictly versioned `/api/v1` API contracts, request validation, audio modality upload ingestion guardrails, structured JSON logging with correlation request IDs, and unified error handling.
> - **Phase 2**: Real persistent relational database structure (PostgreSQL / Supabase + SQLAlchemy 2.0 ORM), migrations, full 13-entity data model, first-class audio persistence foundation, cascade deletion safety, and complete investigation data isolation.
> - **Phase 3**: Real multimodal input ingestion for previously unseen **TEXT**, **IMAGE**, **URL**, and **AUDIO** into a normalized investigation pipeline with database persistence, real Tesseract OCR, real faster-whisper Speech-to-Text, SSRF-protected web extraction, and language detection.
>
> **Phase 3 Scope Notice**:
> Phase 3 implements **REAL INPUT INGESTION**.
> Phase 3 does **NOT** implement:
> - Agentic claim extraction or decomposition (deferred to Phase 4)
> - Web search or evidence retrieval (deferred to Phase 4)
> - NLI or ML verification models (deferred to Phase 4)
> - Final synthesis verdict generation (deferred to Phase 4)
> - Conversational Copilot or Analytics (deferred to Phase 5)

---

## 1. Core Multimodal Ingestion Pipeline (Phase 3)

All four input modalities enter the identical normalized ingestion workflow:

```
User Input (TEXT | IMAGE | URL | AUDIO)
           ↓
Input Validation & Security Guardrails
           ↓
Normalization (Unicode NFC | Container Inspection)
           ↓
Text Extraction / Transcription (OCR | Faster-Whisper | HTML Scraping)
           ↓
Language Detection (English, Hindi, UNKNOWN)
           ↓
NormalizedInput Schema
           ↓
Atomic Database Persistence (investigations + inputs)
           ↓
IngestResponse (investigation_id, input_type, status, extracted content, metadata)
```

---

## 2. Ingestion Modality Specifications

### 1. Text Ingestion (`POST /api/v1/verify/text`)
- **Accepted Inputs**: Single factual claims, multi-sentence paragraphs, news excerpts, or social media statements.
- **Validation**: Enforces minimum length (3 characters), maximum size (50,000 characters), and non-blank input.
- **Normalization**: Unicode NFC normalization, excessive whitespace and line break cleaning.
- **Multi-Claim Preservation**: Preserves raw content containing multiple factual statements without premature claim splitting.
- **Metadata**: Calculates SHA-256 content hash, word count, and character count.

### 2. Image Ingestion & OCR (`POST /api/v1/verify/image`)
- **Accepted Formats**: `PNG`, `JPG`, `JPEG`, `WEBP` (up to 10 MB).
- **Validation**: Enforces MIME type, extension, empty-file check, dimension boundaries (10px to 10,000px), and image corruption detection (`PIL.Image.verify`).
- **Real OCR Engine**: Powered by **Tesseract 5.5.3** (with `pytesseract`) configured for English (`eng`) and Hindi (`hin`).
- **OCR Outputs**:
  - Full extracted text
  - Average word-level confidence score
  - Bounding box regions with coordinates `(left, top, width, height)` and per-box confidence
- **Security**: Images are hashed (SHA-256); sanitized references (`images/<hash>.<ext>`) are stored without leaking server filesystem paths.

### 3. URL Ingestion & Web Extraction (`POST /api/v1/verify/url`)
- **Accepted Inputs**: Public `http://` and `https://` URLs.
- **Strong SSRF Protection**:
  - Rejects `localhost`, `127.0.0.1`, `::1`, and cloud metadata IPs (`169.254.169.254`, `metadata.google.internal`).
  - Resolves target hostnames against DNS and verifies each resolved IP with `ipaddress` (blocking private, loopback, link-local, multicast, and reserved ranges).
- **Safe Fetching & Extraction**:
  - Strict redirect validation (re-validates every redirect target up to 3 hops).
  - Enforces response size limit (5 MB) and 10s request timeout.
  - Rejects non-HTML/text media types (e.g. video streams, binaries).
  - Parses DOM with **BeautifulSoup** to extract article title, canonical URL, author, publication date, domain, and publisher name.
  - Removes non-content elements (`<script>`, `<style>`, `<nav>`, `<header>`, `<footer>`, `<aside>`, `<noscript>`).

### 4. Audio Ingestion & Real Speech-to-Text (`POST /api/v1/verify/audio`)
- **Accepted Formats**: Multipart upload (`multipart/form-data`) supporting `WAV`, `MP3`, `M4A`, `WEBM`, `MP4`, `OGG`, `FLAC` (up to 25 MB).
- **Container Validation**: Inspects stream integrity and container metadata via **PyAV** (`av.open`), verifying audio channels, sample rate, codec, and duration.
- **Real Speech-to-Text**:
  - Powered by **faster-whisper** (`ctranslate2`) running on-device CPU inference (`tiny` or `base` model).
  - Dynamically transcribes actual spoken words without predefined or hardcoded transcripts.
  - Computes real transcription confidence scores and spoken language detection.
- **Audio Temporary File Security**:
  - Audio bytes are temporarily buffered in a secured temp directory using randomized UUID filenames.
  - `finally:` blocks guarantee immediate unlinking (`os.unlink`) upon transcription completion or failure.
  - Client responses never expose server filesystem paths.
- **Failure Transparency**: If audio contains no recognizable speech or transcription fails, returns structured `transcription_failed` failure without silently fabricating text or switching to demo mode.

---

## 3. Database Persistence & Audio Schema

All ingested inputs persist into the Phase 2 database tables:
- **`investigations`**: Records `id`, `input_type` (`TEXT`, `IMAGE`, `URL`, `AUDIO`), `input_mode` (`LIVE` default, or `DEMO`), status (`received`), and detected language.
- **`inputs`**: Records original content, extracted text, content hash, metadata, and dedicated Phase 2 audio fields:
  - `audio_storage_reference` (e.g. `audio/9a3f...wav`)
  - `audio_filename`
  - `audio_mime_type`
  - `audio_duration`
  - `audio_transcript` (actual generated transcript)
  - `audio_transcription_confidence` (average confidence float)
  - `audio_transcription_status` (`COMPLETED` or `FAILED`)

---

## 4. Configuration & Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `development` | Environment name |
| `DEFAULT_MODE` | `LIVE` | Default execution mode (`LIVE` or `DEMO`) |
| `DATABASE_URL` | `sqlite:///./evidencex_dev.db` | PostgreSQL / Supabase connection URL |
| `SUPABASE_URL` | `""` | Supabase project REST URL |
| `SUPABASE_ANON_KEY` | `""` | Public anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | `""` | Backend service-role key |
| `MAX_AUDIO_SIZE_BYTES` | `26214400` (25 MB) | Maximum audio upload size |
| `MAX_IMAGE_SIZE_BYTES` | `10485760` (10 MB) | Maximum image upload size |
| `STT_PROVIDER` | `whisper` | Speech-to-Text provider (`whisper`, `google`) |
| `WHISPER_MODEL` | `tiny` | Whisper model size (`tiny`, `base`, `small`) |
| `OCR_ENGINE` | `tesseract` | OCR engine (`tesseract`, `paddleocr`) |

---

## 5. Local Setup & Testing

### Prerequisites
- Python 3.11+
- Tesseract OCR (`brew install tesseract tesseract-lang`)

### Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### Run Test Suite (84 Automated Tests)
```bash
PYTHONPATH=. backend/.venv/bin/pytest backend/tests -v
```
Test categories:
- **Phase 1 Tests (34)**: API contracts, routing, CORS, request IDs, error formats, settings.
- **Phase 2 Tests (22)**: Relational schema, cascade deletes, data isolation, audio field initialization.
- **Phase 3 Tests (28)**: Real text ingestion, image OCR (PNG/JPEG), SSRF URL blocking & article extraction, real audio Whisper Speech-to-Text transcription, and DB persistence.

---

## 6. Known Limitations (Phase 3 Boundary)

- **Claim Extraction**: Ingested inputs preserve the full raw or extracted text without breaking them down into atomic claims (scheduled for Phase 4).
- **Web Verification**: Verification verdicts and external source evidence retrieval are strictly not active in Phase 3.
- **Audio Quality**: Whisper model performance is dependent on audio clarity and background noise. Silent or unintelligible audio returns a transparent `transcription_failed` response.
