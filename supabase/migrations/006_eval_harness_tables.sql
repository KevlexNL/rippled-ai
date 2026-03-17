-- Eval harness tables — WO-RIPPLED-EVAL-HARNESS
-- Run against the Supabase database to create eval infrastructure.

-- eval_datasets: labeled source items for measuring prompt quality
CREATE TABLE IF NOT EXISTS eval_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_item_id UUID NOT NULL REFERENCES source_items(id) ON DELETE CASCADE,
    expected_has_commitment BOOLEAN NOT NULL,
    expected_commitment_count INTEGER,
    label_notes TEXT,
    labeled_by VARCHAR(100),
    labeled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_eval_datasets_user_id ON eval_datasets(user_id);

-- eval_runs: one row per eval execution with aggregate scores
CREATE TABLE IF NOT EXISTS eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    prompt_version VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    items_tested INTEGER NOT NULL DEFAULT 0,
    true_positives INTEGER NOT NULL DEFAULT 0,
    false_positives INTEGER NOT NULL DEFAULT 0,
    true_negatives INTEGER NOT NULL DEFAULT 0,
    false_negatives INTEGER NOT NULL DEFAULT 0,
    precision_score NUMERIC(5,4),
    recall_score NUMERIC(5,4),
    f1_score NUMERIC(5,4),
    total_cost_estimate NUMERIC(10,6),
    duration_ms INTEGER,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- eval_run_items: per-item results for failure analysis
CREATE TABLE IF NOT EXISTS eval_run_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_run_id UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    source_item_id UUID NOT NULL REFERENCES source_items(id) ON DELETE CASCADE,
    expected_has_commitment BOOLEAN NOT NULL,
    actual_has_commitment BOOLEAN NOT NULL,
    passed BOOLEAN NOT NULL,
    raw_prompt TEXT,
    raw_response TEXT,
    parsed_commitments JSONB,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_estimate NUMERIC(10,6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_eval_run_items_eval_run_id ON eval_run_items(eval_run_id);
