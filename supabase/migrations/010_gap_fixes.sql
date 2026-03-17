-- WO-RIPPLED-FRONTEND-BACKEND-GAP — Gap analysis fixes
--
-- Schema changes required for frontend wiring. All columns were already added
-- via 999_production_catchup.sql; this migration is idempotent confirmation.
--
-- 1. commitments.counterparty_name  — enables "Group by Client" in frontend
-- 2. user_settings.anthropic_api_key_encrypted — LLM key storage
-- 3. user_settings.openai_api_key_encrypted    — LLM key storage

ALTER TABLE commitments ADD COLUMN IF NOT EXISTS counterparty_name VARCHAR(255);
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS anthropic_api_key_encrypted TEXT;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS openai_api_key_encrypted TEXT;
