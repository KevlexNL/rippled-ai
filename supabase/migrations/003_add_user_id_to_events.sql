-- Run manually in Supabase SQL editor
-- WO-RIPPLED-C6-CALENDAR-FIX: add user_id column to events table
-- Column is nullable for backward compatibility with existing rows

ALTER TABLE events ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
