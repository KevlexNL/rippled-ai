-- Migration 020: Add user_id to surfacing_audit
-- WO-3: Ensure surfacing_audit has user_id with FK to users(id)
--
-- Note: This column may already exist from ORM auto-creation or prior manual work.
-- All statements are idempotent (IF NOT EXISTS / DO $$ guard).

-- Step 1: Add column if it doesn't exist (allow NULL initially for safety)
ALTER TABLE surfacing_audit ADD COLUMN IF NOT EXISTS user_id UUID;

-- Step 2: Add FK constraint if not already present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'surfacing_audit_user_id_fkey'
          AND table_name = 'surfacing_audit'
    ) THEN
        ALTER TABLE surfacing_audit
            ADD CONSTRAINT surfacing_audit_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Step 3: Backfill NULL user_ids from the commitment's user_id
UPDATE surfacing_audit sa
SET user_id = c.user_id
FROM commitments c
WHERE sa.commitment_id = c.id
  AND sa.user_id IS NULL;

-- Step 4: Make NOT NULL (only safe after backfill)
-- Guard: only alter if column is currently nullable
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'surfacing_audit'
          AND column_name = 'user_id'
          AND is_nullable = 'YES'
    ) THEN
        ALTER TABLE surfacing_audit ALTER COLUMN user_id SET NOT NULL;
    END IF;
END $$;

-- Step 5: Add index for user_id lookups
CREATE INDEX IF NOT EXISTS ix_surfacing_audit_user_id ON surfacing_audit(user_id);
