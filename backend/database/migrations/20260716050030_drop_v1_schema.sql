-- Drop v1 watchlist and alerts tables. v2 (user_watchlist, price_alerts)
-- is the canonical implementation. v1 was never removed during the
-- v1→v2 migration (20260706130000 created v2 alongside v1). These tables
-- have been verified to have no production code references; only the
-- migration tests and the generated frontend types reference them.
--
-- Re-confirmed 2026-07-22 before applying: both tables hold 0 rows, the v2
-- tables carry the live data (user_watchlist=17, price_alerts=3), and a grep
-- over backend/src + frontend src finds no runtime reference — only the
-- auto-generated Supabase type files, which regenerate to drop the unused defs.
BEGIN;

DROP TABLE IF EXISTS public.psx_watchlist;
DROP TABLE IF EXISTS public.psx_alerts;

INSERT INTO public._applied_migrations (filename, applied_at)
VALUES ('20260716050030_drop_v1_schema.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
