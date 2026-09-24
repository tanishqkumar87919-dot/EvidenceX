-- EvidenceX Phase 6: Verification Engine Schema & Constraints
-- Updates investigation and claim status checks, verdict checks, and adds verification_results columns

-- 1. Update status check constraints on investigations
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
        'verifying',
        'verified',
        'verification_partial',
        'completed',
        'failed',
        'degraded'
    ));

-- 2. Update status check constraints on claims
ALTER TABLE claims DROP CONSTRAINT IF EXISTS claims_status_check;
ALTER TABLE claims ADD CONSTRAINT claims_status_check
    CHECK (status IN (
        'extracted',
        'decomposing',
        'tasks_created',
        'ready_for_retrieval',
        'evidence_retrieved',
        'ready_for_verification',
        'verifying',
        'verified',
        'investigating',
        'unverified',
        'failed'
    ));

-- 3. Update verdict check constraints on verification_results
ALTER TABLE verification_results DROP CONSTRAINT IF EXISTS verification_results_verdict_check;
ALTER TABLE verification_results ADD CONSTRAINT verification_results_verdict_check
    CHECK (verdict IN (
        'SUPPORTED',
        'REFUTED',
        'CONTRADICTED',
        'PARTIALLY_SUPPORTED',
        'INCONCLUSIVE',
        'INSUFFICIENT_EVIDENCE'
    ));

-- 4. Add Phase 6 columns to verification_results if they do not exist
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS evidence_strength NUMERIC(5, 4);
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS supporting_evidence_ids JSONB DEFAULT '[]'::jsonb;
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS contradicting_evidence_ids JSONB DEFAULT '[]'::jsonb;
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS uncertainty TEXT;
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS model_provider VARCHAR(100);
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- 5. Additional index on verification_results
CREATE INDEX IF NOT EXISTS idx_verification_results_verdict ON verification_results(verdict);
