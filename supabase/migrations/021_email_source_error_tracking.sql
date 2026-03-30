-- Add error tracking columns to sources table for per-source error isolation.
-- Idempotent: uses IF NOT EXISTS via DO block.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sources' AND column_name = 'last_error'
    ) THEN
        ALTER TABLE sources ADD COLUMN last_error TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sources' AND column_name = 'last_error_at'
    ) THEN
        ALTER TABLE sources ADD COLUMN last_error_at TIMESTAMPTZ;
    END IF;
END $$;
