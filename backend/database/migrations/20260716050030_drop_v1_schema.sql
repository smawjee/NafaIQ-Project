-- Drop v1 watchlist and alerts tables. v2 (user_watchlist, price_alerts)
-- is the canonical implementation. v1 was never removed during the
-- v1→v2 migration (20260706130000 created v2 alongside v1). These tables
-- have been verified to have no production code references; only the
-- migration tests and RLS hardening scripts reference them.
BEGIN;

DROP TABLE IF EXISTS public.psx_watchlist;
DROP TABLE IF EXISTS public.psx_alerts;

COMMIT;
