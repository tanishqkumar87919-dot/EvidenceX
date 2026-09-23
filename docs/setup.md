# EvidenceX - Repository & Environment Setup Guide

This document explains the architectural setup, secret management, database workflow, and connection flows for EvidenceX.

---

## 1. GitHub Repository Setup

- **Canonical Repository:** `https://github.com/tanishqkumar87919-dot/EvidenceX.git`
- **Default Branch:** `main`
- **Remote Configuration:**
  ```bash
  git remote -v
  # origin  https://github.com/tanishqkumar87919-dot/EvidenceX.git (fetch)
  # origin  https://github.com/tanishqkumar87919-dot/EvidenceX.git (push)
  ```
- **Rules:**
  - Never commit credentials, `.env` files, or production secrets.
  - All database schema updates must be tracked via version-controlled migrations under `supabase/migrations/`.

---

## 2. Supabase Setup

EvidenceX uses **Supabase (PostgreSQL)** for persistence, Row Level Security (RLS), and evidence intelligence storage.

### Required Steps:
1. Log in to [Supabase](https://supabase.com) and access or create your EvidenceX project.
2. Under **Project Settings > API**, retrieve:
   - **Project URL** (`https://<project-ref>.supabase.co`)
   - **anon / public key** (safe for frontend)
   - **service_role secret key** (strict backend-only access)
3. Under **Project Settings > Database**, retrieve your PostgreSQL connection string:
   - `postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres`

---

## 3. Required Environment Variables

All configuration is provided via environment variables. See [`.env.example`](../.env.example).

### Public / Frontend-Safe Variables
*Prefix with `NEXT_PUBLIC_` for Next.js browser exposure:*
- `NEXT_PUBLIC_APP_ENV`: Deployment stage (`development` | `staging` | `production`).
- `NEXT_PUBLIC_APP_URL`: Frontend URL (e.g. `http://localhost:3000`).
- `NEXT_PUBLIC_API_BASE_URL`: Backend API endpoint (e.g. `http://localhost:8000/api/v1`).
- `NEXT_PUBLIC_SUPABASE_URL`: Supabase project endpoint.
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`: Supabase public anonymous key (RLS enforced).

### Private / Backend-Only Variables
*CRITICAL: NEVER expose these to frontend bundles or Git repositories:*
- `SUPABASE_SERVICE_ROLE_KEY`: Superuser admin key bypassing RLS.
- `DATABASE_URL`: Direct PostgreSQL connection string.
- `SEARCH_PROVIDER`: Web search provider (`tavily` | `serper`).
- `SEARCH_API_KEY`: API key for search engine.
- `FACT_CHECK_PROVIDER`: Fact-checking API provider (`google_factcheck`).
- `FACT_CHECK_API_KEY`: Fact-checking API credentials.
- `CORS_ORIGINS`: Allowed CORS origin list.

---

## 4. Local Development Setup

### Backend (FastAPI)
```bash
# 1. Create and activate virtual environment
python3 -m venv backend/.venv
source backend/.venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Configure local environment
cp .env.example .env
# Edit .env with your Supabase credentials

# 4. Run tests
pytest backend/tests

# 5. Start development server
uvicorn backend.app.main:app --reload --port 8000
```
- OpenAPI Documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/v1/health`

### Frontend (Next.js)
```bash
# Install frontend dependencies
npm install

# Configure local env
cp .env.example .env.local

# Run frontend development server
npm run dev
```

---

## 5. Database Migration Workflow

- Migrations live under `supabase/migrations/`.
- Every schema change must be a distinct, sequentially numbered `.sql` file:
  - `00001_initial_extensions.sql`
  - `00002_create_investigations_and_claims.sql`
- Standards:
  - Primary Keys: UUID v4 (`gen_random_uuid()`)
  - Timestamps: `created_at` and `updated_at` with `TIMESTAMPTZ` and auto-update trigger.
  - Row Level Security (RLS) enabled on all tables.
  - Development and production databases separated cleanly by connection strings.

---

## 6. Secret-Management Rules

1. **Zero Secret Policy in Git:**
   `.gitignore` excludes all `.env*` files, `.key`, `.pem`, and credential stores.
2. **Key Tier Separation:**
   `SUPABASE_SERVICE_ROLE_KEY` is exclusively read by backend Python workers. It must NEVER have a `NEXT_PUBLIC_` prefix and never appear in client bundles.
3. **Frontend Protection:**
   The frontend only uses `NEXT_PUBLIC_SUPABASE_ANON_KEY` and relies on Supabase Row Level Security (RLS) policies for data isolation.

---

## 7. How Frontend Connects to Backend

```
[Browser / Next.js Client]
        │
        ▼ (HTTP REST / JSON)
[FastAPI Backend: /api/v1]
   ├── /verify/text
   ├── /verify/image
   ├── /verify/url
   ├── /investigations/{id}
   └── /health
```
- The frontend issues requests to `NEXT_PUBLIC_API_BASE_URL`.
- CORS middleware restricts access to authorized origins specified in `CORS_ORIGINS`.

---

## 8. How Backend Connects to Supabase

```
[FastAPI Backend]
        │
        ├─── Direct PostgreSQL Pool (psycopg2 / asyncpg) ──► Port 5432 (DATABASE_URL)
        └─── Supabase REST / Storage Client ──────────────► HTTPS /rest/v1/ (SUPABASE_SERVICE_ROLE_KEY)
```
- Backend connects to Supabase using `DATABASE_URL` for high-throughput relational transactions or Supabase Client with `SUPABASE_SERVICE_ROLE_KEY` for storage and administrative events.
- Health check endpoint (`/api/v1/health`) probes live connectivity and returns actual connection status.
