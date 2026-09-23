# EvidenceX Backend — Phase 4: Agentic Claim Extraction & Decomposition

Welcome to the **EvidenceX Backend Engine**.

EvidenceX is an AI-powered multimodal claim verification and evidence intelligence platform supporting **TEXT**, **IMAGE**, **URL**, and **AUDIO** verification modalities.

> [!IMPORTANT]
> **Implementation Phase Notice**:
> This codebase implements **PHASES 1, 2, 3, & 4**:
> - **Phase 1**: FastAPI foundation, strictly versioned `/api/v1` API contracts, request validation, audio modality upload ingestion guardrails, structured JSON logging with correlation request IDs, and unified error handling.
> - **Phase 2**: Real persistent relational database structure (PostgreSQL / Supabase + SQLAlchemy 2.0 ORM), migrations, full 13-entity data model, first-class audio persistence foundation, cascade deletion safety, and complete investigation data isolation.
> - **Phase 3**: Real multimodal input ingestion for previously unseen **TEXT**, **IMAGE**, **URL**, and **AUDIO** into a normalized investigation pipeline with database persistence, real Tesseract OCR, real faster-whisper Speech-to-Text, SSRF-protected web extraction, and language detection.
> - **Phase 4**: Real agentic claim extraction, atomic claim identification, compound claim decomposition, 12-category taxonomy classification, verification question generation, search query task creation, configurable LLM architecture (`local`, `openai`, `gemini`), and transactional database persistence.
>
> **Phase 4 Scope Notice**:
> Phase 4 implements **AGENTIC CLAIM EXTRACTION, DECOMPOSITION & TASK GENERATION**.
> Phase 4 does **NOT** implement:
> - Web search (Tavily / Serper) or source crawling (deferred to Phase 5)
> - Evidence retrieval, ranking, and source credibility scoring (deferred to Phase 5)
> - NLI or ML verification models (deferred to Phase 5)
> - Final synthesis verdict generation (deferred to Phase 5)
> - Timeline evolution analysis (deferred to Phase 6)
> - Conversational Copilot or Analytics (deferred to Phase 7 & 8)

---

## 1. Core Agentic Claim Investigation Pipeline (Phase 4)

All four input modalities enter the identical normalized investigation pipeline:

```
Normalized Input (TEXT | IMAGE OCR | URL Article | AUDIO Transcript)
                           ↓
               Claim Extraction & Filtering
             (Separates facts from opinions,
               questions, greetings, noise)
                           ↓
             Compound Claim Decomposition
            (Decomposes into independently
               verifiable atomic claims)
                           ↓
             Claim Taxonomy Classification
            (STATISTIC, DATE, LOCATION, etc.)
                           ↓
            Verification Task Generation
           (Question formulation + search
            query planning + source prefs)
                           ↓
            Atomic Database Persistence
           (claims, claim_tasks, timeline,
               agent_events, status)
                           ↓
        Investigation Status: tasks_created
```

---

## 2. Claim Extraction & Decomposition Features

### 1. Atomic Claim Identification & Noise Filtering
- Separates subjective opinions ("I think", "in my opinion"), conversational greetings ("Hello"), rhetorical questions, and boilerplate calls to action from verifiable factual claims.
- Evaluates factual markers (entities, numbers, dates, reporting verbs) to compute an extraction confidence score (0.0 to 1.0).

### 2. Compound Claim Decomposition
- Automatically breaks complex, multi-clause statements into standalone atomic assertions.
- **Example**:
  `"The WHO announced in Geneva on May 5th, 2023 that COVID-19 is no longer a global health emergency."`
  Decomposes into:
  1. *Core assertion*: "The WHO announced that COVID-19 is no longer a global health emergency."
  2. *Temporal claim*: "The announcement occurred on May 5th, 2023."
  3. *Location claim*: "The announcement was made in Geneva."
- Each atomic claim is independently verifiable.

### 3. Claim Taxonomy (12 Standard Categories)
Each atomic claim is classified into:
- `EVENT`: Discrete occurrences, incidents, announcements, meetings.
- `STATISTIC`: Quantified data, percentages, numeric measurements.
- `DATE`: Specific temporal assertions, historical dates.
- `LOCATION`: Geographic places, facilities, cities, countries.
- `PERSON`: Individual figures, public officials, executives.
- `ORGANIZATION`: Agencies, institutions, NGOs, corporations.
- `QUOTE`: Direct or indirect quotations, official statements.
- `SCIENTIFIC`: Biology, physics, medicine, climate, clinical studies.
- `ECONOMIC`: GDP, inflation, interest rates, financial markets.
- `POLITICAL`: Elections, legislation, treaties, government policy.
- `PRODUCT`: Device specs, pricing, releases, hardware/software.
- `OTHER`: General factual assertions.

### 4. Verification Task & Query Generation
For each atomic claim, the system generates:
- **`task_description`**: A targeted, objective verification question.
- **`search_query`**: Planned search query keywords for future evidence retrieval (Phase 5).
- **`source_preferences`**: Recommended source categories (e.g. `OFFICIAL`, `ACADEMIC`, `REPUTABLE_NEWS`, `GOVERNMENT`, `FACT_CHECK`).
- **`task_status`**: Set to `"pending"`.

---

## 3. Configurable LLM Provider Layer

Configurable via environment variables without hardcoded models:
- **`LLM_PROVIDER="local"` (Default)**: Robust, deterministic NLP claim extractor and decomposer requiring zero external API keys. Highly optimized for test suites and offline environments.
- **`LLM_PROVIDER="openai"`**: Connects to OpenAI or OpenAI-compatible endpoints (Groq, Ollama, DeepSeek) for structured JSON claim extraction.
- **`LLM_PROVIDER="gemini"`**: Connects to Google Gemini OpenAI-compatible endpoints.
- **Transparent Failure Handling**: If an external LLM is selected but the API key is not configured or remote API fails, the backend cleanly raises `LLMProviderUnavailableException` (HTTP 503 `LLM_PROVIDER_UNAVAILABLE`) in LIVE mode. Zero fake demo claims are ever fabricated.

---

## 4. API Endpoints (Phase 4 Updates)

### Active Endpoints
- `POST /api/v1/investigations` (201 Created): Accepts new investigation, runs claim extraction & task creation on input, persists to database, returns investigation detail.
- `GET /api/v1/investigations/{id}` (200 OK): Returns real investigation status (`tasks_created`), modality, mode, and claims count.
- `GET /api/v1/investigations/{id}/status` (200 OK): Returns current lifecycle stage (`TASKS_CREATED`) and progress percentage (40%).
- `GET /api/v1/investigations/{id}/claims` (200 OK): Returns list of extracted atomic claims with their generated verification tasks.
- `GET /api/v1/claims/{claim_id}` (200 OK): Returns single claim detail with its associated tasks.
- `POST /api/v1/verify/text`, `/image`, `/url`, `/audio` (200 OK): Ingests multimodal input, runs claim extraction, and includes `claims_count`, `tasks_count`, and `claim_extraction_status` in `metadata`.
- `GET /api/v1/system/status` (200 OK): Subsystem `claim_extractor` reports `"phase_4_ready"`.

### Future Endpoints (Strictly 501 Service Not Ready)
- `GET /api/v1/investigations/{id}/evidence` (Phase 5)
- `GET /api/v1/investigations/{id}/timeline` (Phase 6)
- `POST /api/v1/investigations/{id}/copilot` (Phase 7)
- `GET /api/v1/analytics/*` (Phase 8)

---

## 5. Automated Test Suite (109 Tests Passing)

Run all tests:
```bash
backend/.venv/bin/python -m pytest backend/tests -v
```

Distribution:
- **Phase 1 (34 tests)**: API contracts, routing, CORS, request IDs, error formats, settings.
- **Phase 2 (22 tests)**: Database schema, models, migrations, cascade deletes, data isolation.
- **Phase 3 (28 tests)**: Text ingestion, image OCR (Tesseract), URL SSRF blocking, audio Speech-to-Text (faster-whisper).
- **Phase 4 (25 tests)**: Compound claim decomposition, noise filtering, task generation, search query planning, taxonomy classification, database persistence, API endpoints, and provider error handling.
