-- Feedback schema tables — WO-RIPPLED-FEEDBACK-SCHEMA
-- Three-tier feedback system for commitment detection improvement.

-- Tier 2: signal_feedback — extraction review
CREATE TABLE IF NOT EXISTS signal_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    detection_audit_id UUID REFERENCES detection_audit(id) ON DELETE SET NULL,
    source_item_id UUID REFERENCES source_items(id) ON DELETE SET NULL,
    reviewer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    extraction_correct BOOLEAN,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    missed_commitments TEXT,
    false_positives TEXT,
    notes TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_signal_feedback_user_id ON signal_feedback(user_id);
CREATE INDEX IF NOT EXISTS ix_signal_feedback_source_item_id ON signal_feedback(source_item_id);

-- Tier 2: outcome_feedback — outcome review
CREATE TABLE IF NOT EXISTS outcome_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    commitment_id UUID NOT NULL REFERENCES commitments(id) ON DELETE CASCADE,
    reviewer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    was_useful BOOLEAN,
    usefulness_rating INTEGER CHECK (usefulness_rating BETWEEN 1 AND 5),
    was_timely BOOLEAN,
    notes TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_outcome_feedback_user_id ON outcome_feedback(user_id);
CREATE INDEX IF NOT EXISTS ix_outcome_feedback_commitment_id ON outcome_feedback(commitment_id);

-- Tier 3: adhoc_signals — Telegram ad-hoc input
CREATE TABLE IF NOT EXISTS adhoc_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'telegram',
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    match_status VARCHAR(20) DEFAULT 'pending',
    matched_commitment_id UUID REFERENCES commitments(id) ON DELETE SET NULL,
    matched_source_item_id UUID REFERENCES source_items(id) ON DELETE SET NULL,
    match_checked_at TIMESTAMPTZ,
    match_confidence NUMERIC(4,3),
    was_found BOOLEAN,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_adhoc_signals_user_id ON adhoc_signals(user_id);
CREATE INDEX IF NOT EXISTS ix_adhoc_signals_match_status ON adhoc_signals(match_status);
CREATE INDEX IF NOT EXISTS ix_adhoc_signals_received_at ON adhoc_signals(received_at);

-- Tier 1: llm_judge_runs — automated LLM-as-judge self-improvement
CREATE TABLE IF NOT EXISTS llm_judge_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    judge_model VARCHAR(100) NOT NULL,
    student_model VARCHAR(100) NOT NULL,
    items_reviewed INTEGER NOT NULL DEFAULT 0,
    false_positives_found INTEGER NOT NULL DEFAULT 0,
    false_negatives_found INTEGER NOT NULL DEFAULT 0,
    prompt_improvement_suggestions JSONB,
    raw_judge_output TEXT,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
