# EvidenceX Backend — Phase 2: Real Investigation Database & Supabase/PostgreSQL

Welcome to the **EvidenceX Backend Engine**.

EvidenceX is a multimodal claim verification and evidence intelligence platform supporting **TEXT**, **IMAGE**, **URL**, and **AUDIO** verification modalities.

> [!IMPORTANT]
> **Implementation Phase Notice**:
> This codebase implements **PHASE 1 & PHASE 2**:
> - **Phase 1**: FastAPI foundation, strictly versioned `/api/v1` API contracts, request validation, audio modality upload ingestion guardrails, structured JSON logging with correlation request IDs, and unified error handling.
> - **Phase 2**: Real persistent relational database structure (PostgreSQL / Supabase + SQLAlchemy 2.0 ORM), migrations, full 13-entity data model, first-class audio persistence foundation (empty/PENDING guarantees), cascade deletion safety, and complete investigation data isolation.
>
> **Phase 2 creates the persistent database foundation. Actual AI processing is NOT implemented yet.**
> Neither OCR, Whisper/Speech-to-Text, claim extraction LLMs, NLI/ML models, nor web search evidence retrieval are active in Phase 2.

---

## 1. Database Architecture & Entities (Phase 2)

The database schema defines 13 relational entities structured for dynamic, live investigations without relying on predefined demo data:

| Entity | Table | Purpose | Cascade / Deletion Behavior |
| --- | --- | --- | --- |
| **01. Users** | `users` | User profile & authentication foundation | Owns investigations and settings |
| **02. Investigations** | `investigations` | Top-level investigation runs (`LIVE` by default, or `DEMO`) | Cascades to all child records below |
| **03. Inputs** | `inputs` | Raw multimodal input records (TEXT, IMAGE, URL, and full AUDIO fields) | `ON DELETE CASCADE` |
| **04. Claims** | `claims` | Atomic verifiable claims extracted from input | `ON DELETE CASCADE` |
| **05. Claim Tasks** | `claim_tasks` | Agentic search/verification sub-tasks per claim | `ON DELETE CASCADE` |
| **06. Sources** | `sources` | Canonical web sources and publishers (deduplicated by URL) | `ON DELETE RESTRICT` (reusable across investigations) |
| **07. Evidence** | `evidence` | Specific relevant excerpts and source assessments | Linked to source via RESTRICT |
| **08. Claim Evidence** | `claim_evidence` | Junction table relating claims to evidence (`SUPPORTING`, `CONTRADICTING`, `INCONCLUSIVE`) | `ON DELETE CASCADE` |
| **09. Verification Results** | `verification_results` | Synthesis verdicts (`SUPPORTED`, `REFUTED`, `INSUFFICIENT_EVIDENCE`), confidence, counts | `ON DELETE CASCADE` |
| **10. Timeline Events** | `timeline_events` | Chronological claim emergence and consensus evolution events | `ON DELETE CASCADE` |
| **11. Agent Events** | `agent_events` | Real-time audit trace of agent execution stages | `ON DELETE CASCADE` |
| **12. Copilot Messages** | `copilot_messages` | Evidence-grounded conversational Q&A history | `ON DELETE CASCADE` |
| **13. User Settings** | `user_settings` | Theme, language, depth, and evidence weighting preferences | `ON DELETE CASCADE` |

---

## 2. First-Class Audio Persistence Foundation

Audio is an equal, first-class input modality using the identical investigation schema as Text, Image, and URL.
In `inputs`:
- `audio_storage_reference`: Storage URI / bucket path
- `audio_filename`: Original file name (e.g. `recording.wav`)
- `audio_mime_type`: MIME type (e.g. `audio/wav`, `audio/mpeg`)
- `audio_duration`: Duration in seconds
- `audio_transcript`: Strictly `NULL` in Phase 2 (populated in Phase 3 via real Speech-to-Text)
- `audio_transcription_confidence`: Strictly `NULL` in Phase 2
- `audio_transcription_status`: Strictly `PENDING` by default

---

## 3. Data Isolation & LIVE/DEMO Guarantees

1. **Strict Investigation Isolation**: All queries and repositories require explicit `investigation_id` filtering. Two distinct investigations can never cross-pollinate claims, inputs, evidence, or events.
2. **LIVE vs. DEMO Separation**: `input_mode` defaults strictly to `LIVE`. Live submissions never silently fall back to demo data.
3. **Safe Cascade Deletion**: Deleting an investigation cleans up all child inputs, claims, tasks, results, timeline events, agent logs, and copilot threads, while preserving shared source records.

---

## 4. Setup & Migrations

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ / Supabase

### Running Migrations
Migrations are located in `supabase/migrations/`:
- `00001_initial_extensions.sql`: Enables `uuid-ossp`, `pgcrypto`, and `update_updated_at_column()` helper.
- `00002_create_investigation_schema.sql`: Complete DDL for all 13 tables, indexes, cascade rules, triggers, and Row Level Security (RLS) policies.

To apply migrations on Supabase:
```bash
# Apply via Supabase CLI
supabase db push
# or run supabase/migrations/00002_create_investigation_schema.sql directly in the Supabase SQL Editor
```

### Environment Configuration
Configure in `.env`:
```bash
# Supabase REST Configuration
SUPABASE_URL=https://<your-project-id>.supabase.co
SUPABASE_ANON_KEY=<your-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>

# Direct PostgreSQL Connection
DATABASE_URL=postgresql://postgres:<password>@db.<your-project-id>.supabase.co:5432/postgres
```

---

## 5. Running the Application & Tests

### Start Local Server
```bash
backend/.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run Automated Tests (63 Tests)
```bash
PYTHONPATH=. backend/.venv/bin/pytest backend/tests -v
```
Test suite includes:
- Phase 1 API routing, validation, CORS, request IDs, error formats, and audio upload guardrails.
- Phase 2 database schema integrity, connection, cascade deletions, isolation, audio field initial state, and LIVE/DEMO separation.
