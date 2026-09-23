# EvidenceX

> **Multimodal AI-Powered Claim Verification & Evidence Intelligence Platform**

EvidenceX analyzes text, screenshots/images, URLs, and audio recordings/speech to decompose claims into verifiable atomic facts, retrieve and analyze real-world evidence, compare supporting and contradicting sources, and generate explainable, evidence-backed verdicts.

---

## Project Status

- **Phase:** Frontend Complete & Audited (10/10 Pages with Multimodal Text, Image, URL & Audio Input)
- **Repository:** `https://github.com/tanishqkumar87919-dot/EvidenceX.git`
- **Database:** Supabase (PostgreSQL with RLS & Migrations)
- **Backend:** Python 3.11+ / FastAPI
- **Frontend:** Analytical Glassmorphic UI (HTML5 / Vanilla CSS / ES6 JavaScript) with Light/Dark Mode & English/Hindi i18n

---

## Frontend Pages (10/10 Complete)

The complete analytical frontend suite is located in [`frontend/`](frontend/) with zero build step required:

| Page | File | Purpose |
| --- | --- | --- |
| **01. Home / Landing** | [`frontend/evidencex.html`](frontend/evidencex.html) | Public platform overview, methodology principles, sample report preview |
| **02. Verification Center** | [`frontend/verification-center.html`](frontend/verification-center.html) | Multimodal intake workspace (Text, Screenshots/Images, URLs, Audio) with depth options |
| **03. Investigation Pipeline** | [`frontend/investigation.html`](frontend/investigation.html) | 7-stage live decomposition & verification progress tracker with agent logs |
| **04. Verification Results** | [`frontend/results.html`](frontend/results.html) | Synthesis dashboard: verdict, confidence, stance breakdown, evidence conflict graph |
| **05. Claim Investigation** | [`frontend/claim-investigation.html`](frontend/claim-investigation.html) | Single-claim deep-dive: source assessment factors, temporal context, AI reasoning trace |
| **06. Evidence Explorer** | [`frontend/evidence-explorer.html`](frontend/evidence-explorer.html) | Research workbench: full-text evidence filtering, source detail drawer, citation audit |
| **07. Evidence Timeline** | [`frontend/evidence-timeline.html`](frontend/evidence-timeline.html) | Chronological claim evolution, consensus tracking, early vs. latest evidence comparison |
| **08. Analytics Dashboard** | [`frontend/analytics.html`](frontend/analytics.html) | Aggregated verification activity, verdict distribution, source diversity analytics |
| **09. AI Copilot** | [`frontend/copilot.html`](frontend/copilot.html) | Evidence-grounded retrieval-augmented investigation assistant with citations |
| **10. Settings** | [`frontend/settings.html`](frontend/settings.html) | Theme (Light/Dark), Language (EN/HI), verification depth, privacy controls, telemetry |

---

### Running the Frontend Locally

```bash
# Serve static frontend workspace locally
python3 -m http.server 3000

# Open in browser:
# http://localhost:3000 (redirects to frontend/evidencex.html)
# or open frontend/evidencex.html directly in any modern browser
```

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
