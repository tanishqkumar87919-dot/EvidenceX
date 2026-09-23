# EvidenceX

> **Multimodal AI-Powered Claim Verification & Evidence Intelligence Platform**

EvidenceX analyzes text, screenshots/images, and online content to decompose claims into verifiable atomic facts, retrieve and analyze real-world evidence, compare supporting and contradicting sources, and generate explainable, evidence-backed verdicts.

---

## Project Status

- **Phase:** Repository & Foundation Setup (Phase 0 Complete)
- **Repository:** `https://github.com/tanishqkumar87919-dot/EvidenceX.git`
- **Database:** Supabase (PostgreSQL with RLS & Migrations)
- **Backend:** Python 3.11+ / FastAPI
- **Frontend:** Next.js / TypeScript / Tailwind CSS

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │        EvidenceX Next.js UI         │
                      │  (Verification Center, Timeline,     │
                      │   Explorer, Results, Copilot)        │
                      └──────────────────┬───────────────────┘
                                         │
                         REST / JSON API │ NEXT_PUBLIC_API_BASE_URL
                                         ▼
                      ┌──────────────────────────────────────┐
                      │         FastAPI Backend Engine       │
                      │       (/api/v1/health, /verify)      │
                      └────────┬───────────────────┬─────────┘
                               │                   │
               PostgreSQL / RLS│                   │ REST / Storage
                 (DATABASE_URL)│                   │ (SERVICE_ROLE_KEY)
                               ▼                   ▼
                      ┌──────────────────────────────────────┐
                      │          Supabase Platform           │
                      │  - PostgreSQL 15+                    │
                      │  - Row Level Security (RLS)          │
                      │  - Storage (Screenshots / Uploads)   │
                      └──────────────────────────────────────┘
```

---

## Quick Start

### 1. Environment Configuration
Copy the template and populate environment variables:
```bash
cp .env.example .env
```
Refer to [`docs/setup.md`](docs/setup.md) for detailed variable descriptions.

### 2. Backend Setup
```bash
# Set up Python virtual environment
python3 -m venv backend/.venv
source backend/.venv/bin/activate

# Install requirements
pip install -r backend/requirements.txt

# Run health tests
PYTHONPATH=. pytest backend/tests

# Start FastAPI server
uvicorn backend.app.main:app --reload --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

### 3. Database Migrations
Migrations are managed in `supabase/migrations/`.
- Refer to [`supabase/migrations/README.md`](supabase/migrations/README.md) for conventions and migration workflow.

---

## Security & Secrets
- Never commit credentials or `.env` files to git.
- Client applications only access public Supabase keys (`NEXT_PUBLIC_SUPABASE_ANON_KEY`).
- `SUPABASE_SERVICE_ROLE_KEY` is strictly reserved for backend server environments.
