-- Admin panel — WO-RIPPLED-ADMIN-PANEL
-- Add is_super_admin flag to user_settings for admin access control.

ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT false;
