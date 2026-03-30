-- Common Terms: domain vocabulary for transcript enrichment
-- Each user can define canonical terms with aliases that resolve during detection.

CREATE TABLE IF NOT EXISTS common_terms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    canonical_term VARCHAR(255) NOT NULL,
    context TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS common_term_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term_id UUID NOT NULL REFERENCES common_terms(id) ON DELETE CASCADE,
    alias VARCHAR(255) NOT NULL,
    source VARCHAR(100) DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(term_id, alias)
);

CREATE INDEX IF NOT EXISTS ix_common_terms_user_id ON common_terms(user_id);
CREATE INDEX IF NOT EXISTS ix_common_term_aliases_term_id ON common_term_aliases(term_id);
CREATE INDEX IF NOT EXISTS ix_common_term_aliases_alias ON common_term_aliases(alias);
