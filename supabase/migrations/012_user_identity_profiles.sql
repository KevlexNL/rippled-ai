CREATE TABLE IF NOT EXISTS user_identity_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    identity_type VARCHAR(50) NOT NULL,
    identity_value VARCHAR(255) NOT NULL,
    source VARCHAR(100),
    confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, identity_type, identity_value)
);

CREATE INDEX IF NOT EXISTS ix_uip_user_id ON user_identity_profiles(user_id);
CREATE INDEX IF NOT EXISTS ix_uip_value ON user_identity_profiles(identity_value);
