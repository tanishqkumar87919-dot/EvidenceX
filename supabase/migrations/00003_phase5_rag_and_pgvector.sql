-- EvidenceX Phase 5: pgvector extension, evidence_chunks table, and Phase 5 lifecycle statuses

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Update status check constraints on investigations
ALTER TABLE investigations DROP CONSTRAINT IF EXISTS investigations_status_check;
ALTER TABLE investigations ADD CONSTRAINT investigations_status_check
    CHECK (status IN (
        'received',
        'queued',
        'processing',
        'tasks_created',
        'ready_for_retrieval',
        'retrieving_evidence',
        'ready_for_verification',
        'no_evidence_found',
        'completed',
        'failed',
        'degraded'
    ));

-- 3. Update status check constraints on claims
ALTER TABLE claims DROP CONSTRAINT IF EXISTS claims_status_check;
ALTER TABLE claims ADD CONSTRAINT claims_status_check
    CHECK (status IN (
        'extracted',
        'decomposing',
        'tasks_created',
        'ready_for_retrieval',
        'evidence_retrieved',
        'investigating',
        'verified',
        'unverified',
        'failed'
    ));

-- 4. Evidence Chunks Table (RAG Passages with 768-dim Vector Embeddings)
CREATE TABLE IF NOT EXISTS evidence_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    claim_id UUID REFERENCES claims(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    heading TEXT,
    character_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER,
    embedding vector(768),
    embedding_model VARCHAR(100),
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. Performance Indexes
CREATE INDEX IF NOT EXISTS idx_evidence_chunks_investigation ON evidence_chunks(investigation_id);
CREATE INDEX IF NOT EXISTS idx_evidence_chunks_claim ON evidence_chunks(claim_id);
CREATE INDEX IF NOT EXISTS idx_evidence_chunks_source ON evidence_chunks(source_id);

-- Cosine similarity HNSW index for high-speed vector retrieval
CREATE INDEX IF NOT EXISTS idx_evidence_chunks_embedding 
    ON evidence_chunks USING hnsw (embedding vector_cosine_ops);
