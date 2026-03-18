-- Add dormant and confirmed values to lifecycle_state enum
-- IF NOT EXISTS prevents errors if values already exist (Postgres 9.6+)
ALTER TYPE lifecycle_state ADD VALUE IF NOT EXISTS 'dormant';
ALTER TYPE lifecycle_state ADD VALUE IF NOT EXISTS 'confirmed';
