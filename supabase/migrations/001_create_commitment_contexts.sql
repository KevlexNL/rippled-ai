-- Run manually in Supabase SQL editor
-- Creates the commitment_contexts table and adds context_id FK to commitments.

-- 1. Create commitment_contexts table
CREATE TABLE IF NOT EXISTS commitment_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_commitment_contexts_user_id ON commitment_contexts(user_id);

-- 2. Add context_id FK to commitments
ALTER TABLE commitments
    ADD COLUMN IF NOT EXISTS context_id UUID REFERENCES commitment_contexts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_commitments_context_id ON commitments(context_id);
