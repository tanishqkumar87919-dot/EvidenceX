# EvidenceX Database Migration Workflow

This directory contains version-controlled database migrations for EvidenceX using PostgreSQL / Supabase.

---

## Migration Workflow Standards

### 1. File Naming Convention
Migrations must follow sequential numbering or ISO timestamp ordering:
`00001_baseline_schema.sql` or `YYYYMMDDHHMMSS_action_target.sql`

Examples:
- `00001_initial_extensions.sql`
- `00002_create_investigations_and_claims.sql`
- `00003_add_evidence_and_sources.sql`

### 2. Primary Keys & UUID Conventions
- Always use UUID v4 for entity IDs:
  ```sql
  id UUID PRIMARY KEY DEFAULT gen_random_uuid()
  ```
- Do not use auto-incrementing serial integers for distributed or public-facing entities.

### 3. Timestamp Conventions
- Use `TIMESTAMPTZ` (UTC with timezone):
  ```sql
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
  ```
- Maintain an `update_updated_at_column()` trigger function to automatically update `updated_at` on row updates.

### 4. Foreign Key Conventions
- Explicit constraint naming: `fk_<source_table>_<target_table>`
- Specify deletion rules explicitly:
  - Strong parent-child relationship (e.g., claims belonging to an investigation): `ON DELETE CASCADE`
  - Soft or shared relationship (e.g., sources referenced across multiple claims): `ON DELETE SET NULL` or `RESTRICT`

### 5. Indexing Strategy
Index high-traffic query filters:
- Foreign keys: `investigation_id`, `claim_id`, `source_id`
- Filtering / state columns: `status`, `input_mode` (LIVE vs DEMO)
- Temporal ordering: `created_at DESC`
- URL / Domain lookup: `url`, `domain` (using B-tree or hash index where appropriate)

### 6. Row Level Security (RLS) Strategy
- RLS is ENABLED by default on all public tables:
  ```sql
  ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;
  ```
- Public/Anonymous users have restricted READ-ONLY access to verified public investigations:
  ```sql
  CREATE POLICY "Public investigations are viewable by everyone" 
  ON investigations FOR SELECT USING (true);
  ```
- Service Role (`SUPABASE_SERVICE_ROLE_KEY`) bypasses RLS and handles backend inserts/updates.

### 7. Environment Separation
- **Development**: Local Supabase or dedicated Dev Supabase project.
- **Production**: Dedicated Production Supabase project.
- Environment switching managed strictly via `DATABASE_URL` and `SUPABASE_URL` in environment variables.

---

## Schema Entity Blueprint (To be implemented in Phase 2)
The forthcoming database schema defines:
1. `users` — User profiles and authentication
2. `investigations` — Core investigation runs (LIVE or DEMO)
3. `inputs` — Original raw text, images, or URLs submitted
4. `claims` — Atomic factual claims extracted from input
5. `claim_tasks` — Search and verification tasks dispatched per claim
6. `sources` — Distinct web sources and publications retrieved
7. `evidence` — Passages and excerpts assessed for claims
8. `claim_evidence` — Junction table linking evidence to claims with relationships
9. `verification_results` — Final synthesis verdicts (SUPPORTED / REFUTED / INSUFFICIENT_EVIDENCE)
10. `timeline_events` — Chronological timeline of events/reporting
11. `agent_events` — Real execution activity trace of agents
12. `copilot_messages` — Grounded Q&A conversation history
13. `user_settings` — UI and investigation preferences
