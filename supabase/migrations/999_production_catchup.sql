-- =============================================================================
-- Production Catchup Migration — WO-RIPPLED-SCHEMA-AUDIT
-- Run this once in Supabase SQL Editor to ensure all columns exist.
-- All statements are idempotent (IF NOT EXISTS / IF NOT EXISTS).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. commitment_contexts table (from manual migration 001 / Alembic context_layer)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS commitment_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_commitment_contexts_user_id ON commitment_contexts(user_id);

-- ---------------------------------------------------------------------------
-- 2. commitments.context_id (from manual migration 001 / Alembic context_layer)
-- ---------------------------------------------------------------------------
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS context_id UUID REFERENCES commitment_contexts(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_commitments_context_id ON commitments(context_id);

-- ---------------------------------------------------------------------------
-- 3. events.user_id (from manual migration 003 / Alembic phase_c6)
-- ---------------------------------------------------------------------------
ALTER TABLE events ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS ix_events_user_id ON events(user_id);

-- ---------------------------------------------------------------------------
-- 4. sources.last_synced_at (from manual migration 004 — no Alembic equivalent until now)
-- ---------------------------------------------------------------------------
ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;

-- ---------------------------------------------------------------------------
-- 5. commitments.counterparty_name (from Alembic frontend_backend_gap)
-- ---------------------------------------------------------------------------
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS counterparty_name VARCHAR(255);

-- ---------------------------------------------------------------------------
-- 6. user_settings LLM API keys (from Alembic frontend_backend_gap)
-- ---------------------------------------------------------------------------
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS anthropic_api_key_encrypted TEXT;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS openai_api_key_encrypted TEXT;

-- =============================================================================
-- Done. All columns that have ever been added via Alembic or manual SQL are now
-- guaranteed to exist. Safe to re-run — all statements are idempotent.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 7. commitments.context_tags (added 2026-04-01 — was in ORM but never migrated)
-- ---------------------------------------------------------------------------
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS context_tags JSONB;
