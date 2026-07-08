-- 20260708011922_add_idx_psx_portfolios_user_id.sql
-- Add index on psx_portfolios.user_id to speed up RLS policy lookups
-- (every user-data query hits this index via auth.uid() = user_id)
-- Safe: pure addition, no impact on existing rows, no table drops.

CREATE INDEX IF NOT EXISTS idx_psx_portfolios_user_id
  ON psx_portfolios (user_id);
