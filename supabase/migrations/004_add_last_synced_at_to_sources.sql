-- Manual migration: run via Supabase SQL editor or psql
-- Adds last_synced_at column to sources table for incremental email sync
-- WO-RIPPLED-EMAIL-BACKFILL

ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;
