-- ==============================================================================
-- EvidenceX Database Migration: 00002_create_investigation_schema.sql
-- Real Relational Investigation Schema (Supabase / PostgreSQL)
-- ==============================================================================

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Investigations Table
CREATE TABLE IF NOT EXISTS investigations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(255),
    input_mode VARCHAR(20) NOT NULL DEFAULT 'LIVE' CHECK (input_mode IN ('LIVE', 'DEMO')),
    input_type VARCHAR(20) NOT NULL CHECK (input_type IN ('TEXT', 'IMAGE', 'URL', 'AUDIO')),
    status VARCHAR(50) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'degraded')),
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    verification_depth VARCHAR(20) NOT NULL DEFAULT 'standard' CHECK (verification_depth IN ('quick', 'standard', 'deep')),
    evidence_preference VARCHAR(20) NOT NULL DEFAULT 'balanced' CHECK (evidence_preference IN ('balanced', 'official')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

-- 3. Inputs Table (Supports TEXT, IMAGE, URL, and full AUDIO metadata)
CREATE TABLE IF NOT EXISTS inputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    input_type VARCHAR(20) NOT NULL CHECK (input_type IN ('TEXT', 'IMAGE', 'URL', 'AUDIO')),
    original_text TEXT,
    image_storage_reference VARCHAR(500),
    url VARCHAR(2048),
    extracted_text TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    content_hash VARCHAR(64),
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Dedicated Audio Ingestion Fields
    audio_storage_reference VARCHAR(500),
    audio_filename VARCHAR(255),
    audio_mime_type VARCHAR(100),
    audio_duration NUMERIC(10, 2),
    audio_transcript TEXT DEFAULT NULL,
    audio_transcription_confidence NUMERIC(5, 4) DEFAULT NULL,
    audio_transcription_status VARCHAR(50) NOT NULL DEFAULT 'PENDING' CHECK (audio_transcription_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Claims Table
CREATE TABLE IF NOT EXISTS claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    claim_text TEXT NOT NULL,
    claim_type VARCHAR(50),
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    context TEXT,
    order_index INTEGER NOT NULL DEFAULT 0,
    extraction_confidence NUMERIC(5, 4),
    status VARCHAR(50) NOT NULL DEFAULT 'extracted' CHECK (status IN ('extracted', 'investigating', 'verified', 'unverified')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. Claim Tasks Table
CREATE TABLE IF NOT EXISTS claim_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    task_description TEXT NOT NULL,
    search_query TEXT,
    task_status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (task_status IN ('pending', 'running', 'completed', 'failed')),
    completion_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. Sources Table (Shared across investigations; indexed by URL & Domain)
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url VARCHAR(2048) NOT NULL UNIQUE,
    canonical_url VARCHAR(2048),
    title VARCHAR(500),
    publisher VARCHAR(255),
    domain VARCHAR(255),
    source_type VARCHAR(50),
    author VARCHAR(255),
    publication_date TIMESTAMPTZ,
    retrieved_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. Evidence Table (Linked to source with ON DELETE RESTRICT to prevent source corruption)
CREATE TABLE IF NOT EXISTS evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID REFERENCES claims(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    exact_relevant_excerpt TEXT NOT NULL,
    relationship VARCHAR(50) NOT NULL CHECK (relationship IN ('SUPPORTING', 'CONTRADICTING', 'INCONCLUSIVE')),
    relevance NUMERIC(5, 4),
    source_assessment JSONB DEFAULT '{}'::jsonb,
    temporal_information JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8. Claim Evidence Junction Table
CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    evidence_id UUID NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    relationship VARCHAR(50) NOT NULL DEFAULT 'SUPPORTING' CHECK (relationship IN ('SUPPORTING', 'CONTRADICTING', 'INCONCLUSIVE')),
    relevance_score NUMERIC(5, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (claim_id, evidence_id)
);

-- 9. Verification Results Table
CREATE TABLE IF NOT EXISTS verification_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    claim_id UUID REFERENCES claims(id) ON DELETE CASCADE,
    verdict VARCHAR(50) NOT NULL CHECK (verdict IN ('SUPPORTED', 'REFUTED', 'INSUFFICIENT_EVIDENCE')),
    model_confidence NUMERIC(5, 4),
    evidence_sufficiency VARCHAR(50),
    supporting_count INTEGER NOT NULL DEFAULT 0,
    contradicting_count INTEGER NOT NULL DEFAULT 0,
    inconclusive_count INTEGER NOT NULL DEFAULT 0,
    explanation TEXT,
    generated_timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 10. Timeline Events Table
CREATE TABLE IF NOT EXISTS timeline_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    claim_id UUID REFERENCES claims(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    event_date TIMESTAMPTZ NOT NULL,
    source_reference VARCHAR(500),
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 11. Agent Events Table
CREATE TABLE IF NOT EXISTS agent_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    stage VARCHAR(50),
    message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 12. Copilot Messages Table
CREATE TABLE IF NOT EXISTS copilot_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    message TEXT NOT NULL,
    citations JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 13. User Settings Table
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    theme VARCHAR(20) NOT NULL DEFAULT 'light',
    verification_depth VARCHAR(20) NOT NULL DEFAULT 'standard',
    evidence_preference VARCHAR(20) NOT NULL DEFAULT 'balanced',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ==============================================================================
-- Indexes for High-Traffic Queries & Foreign Key Lookups
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_investigations_user_id ON investigations(user_id);
CREATE INDEX IF NOT EXISTS idx_investigations_input_mode ON investigations(input_mode);
CREATE INDEX IF NOT EXISTS idx_investigations_input_type ON investigations(input_type);
CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status);
CREATE INDEX IF NOT EXISTS idx_investigations_created_at ON investigations(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_inputs_investigation_id ON inputs(investigation_id);
CREATE INDEX IF NOT EXISTS idx_inputs_content_hash ON inputs(content_hash);
CREATE INDEX IF NOT EXISTS idx_inputs_audio_status ON inputs(audio_transcription_status);

CREATE INDEX IF NOT EXISTS idx_claims_investigation_id ON claims(investigation_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);

CREATE INDEX IF NOT EXISTS idx_claim_tasks_claim_id ON claim_tasks(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_tasks_status ON claim_tasks(task_status);

CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url);
CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources(domain);
CREATE INDEX IF NOT EXISTS idx_sources_publication_date ON sources(publication_date DESC);

CREATE INDEX IF NOT EXISTS idx_evidence_claim_id ON evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_evidence_source_id ON evidence(source_id);
CREATE INDEX IF NOT EXISTS idx_evidence_relationship ON evidence(relationship);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_evidence_id ON claim_evidence(evidence_id);

CREATE INDEX IF NOT EXISTS idx_verification_results_investigation_id ON verification_results(investigation_id);
CREATE INDEX IF NOT EXISTS idx_verification_results_claim_id ON verification_results(claim_id);

CREATE INDEX IF NOT EXISTS idx_timeline_events_investigation_id ON timeline_events(investigation_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_date ON timeline_events(event_date ASC);

CREATE INDEX IF NOT EXISTS idx_agent_events_investigation_id ON agent_events(investigation_id);
CREATE INDEX IF NOT EXISTS idx_agent_events_created_at ON agent_events(created_at ASC);

CREATE INDEX IF NOT EXISTS idx_copilot_messages_investigation_id ON copilot_messages(investigation_id);

-- ==============================================================================
-- Triggers for Automatic updated_at Maintenance
-- ==============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
        DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
        CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

        DROP TRIGGER IF EXISTS trg_investigations_updated_at ON investigations;
        CREATE TRIGGER trg_investigations_updated_at BEFORE UPDATE ON investigations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

        DROP TRIGGER IF EXISTS trg_inputs_updated_at ON inputs;
        CREATE TRIGGER trg_inputs_updated_at BEFORE UPDATE ON inputs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

        DROP TRIGGER IF EXISTS trg_claims_updated_at ON claims;
        CREATE TRIGGER trg_claims_updated_at BEFORE UPDATE ON claims FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

        DROP TRIGGER IF EXISTS trg_claim_tasks_updated_at ON claim_tasks;
        CREATE TRIGGER trg_claim_tasks_updated_at BEFORE UPDATE ON claim_tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

        DROP TRIGGER IF EXISTS trg_user_settings_updated_at ON user_settings;
        CREATE TRIGGER trg_user_settings_updated_at BEFORE UPDATE ON user_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- ==============================================================================
-- Row Level Security (RLS) Policies
-- ==============================================================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigations ENABLE ROW LEVEL SECURITY;
ALTER TABLE inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE timeline_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE copilot_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Allow service_role key full administrative access across all tables
DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN
        SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN (
            'users', 'investigations', 'inputs', 'claims', 'claim_tasks', 'sources',
            'evidence', 'claim_evidence', 'verification_results', 'timeline_events',
            'agent_events', 'copilot_messages', 'user_settings'
        )
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS "Service role full access on %I" ON %I;', tbl, tbl);
        EXECUTE format('CREATE POLICY "Service role full access on %I" ON %I FOR ALL USING (auth.role() = ''service_role'') WITH CHECK (auth.role() = ''service_role'');', tbl, tbl);
    END LOOP;
END $$;

-- Allow public read access to completed public investigations and related evidence
DROP POLICY IF EXISTS "Public read access to investigations" ON investigations;
CREATE POLICY "Public read access to investigations" ON investigations FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access to claims" ON claims;
CREATE POLICY "Public read access to claims" ON claims FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access to sources" ON sources;
CREATE POLICY "Public read access to sources" ON sources FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access to evidence" ON evidence;
CREATE POLICY "Public read access to evidence" ON evidence FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access to verification_results" ON verification_results;
CREATE POLICY "Public read access to verification_results" ON verification_results FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read access to timeline_events" ON timeline_events;
CREATE POLICY "Public read access to timeline_events" ON timeline_events FOR SELECT USING (true);
