-- Extend detection_audit with full prompt/response logging columns.
-- WO-RIPPLED-DETECTION-AUDIT-EXTEND

ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50);
ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS raw_prompt TEXT;
ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS raw_response TEXT;
ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS parsed_result JSONB;
ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS tokens_in INTEGER;
ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS tokens_out INTEGER;
ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS cost_estimate NUMERIC(10,6);
ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS model VARCHAR(100);
ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS duration_ms INTEGER;
ALTER TABLE detection_audit ADD COLUMN IF NOT EXISTS error_detail TEXT;
