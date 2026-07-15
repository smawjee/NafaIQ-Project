-- psx_data_source_health: withhold last_error_message from public roles.
--
-- SECURITY. 20260716050000_data_source_health.sql ended with a table-wide
--   GRANT SELECT ON psx_data_source_health TO anon, authenticated;
-- plus an RLS policy of USING (true). The table has a `last_error_message text`
-- column that jobs/scheduler.py::_record_health fills with the raw str(e) of a
-- failed job — that text can carry the Supabase project URL, table names and
-- connection detail.
--
-- The anon key ships in the public browser bundle, so a table-wide SELECT grant
-- means anyone can bypass our API and read the column straight from PostgREST:
--   GET {SUPABASE_URL}/rest/v1/psx_data_source_health?select=last_error_message
--
-- api/health.py::health_sources was already narrowed to an explicit column
-- list, but that only constrains OUR route — it does not close the direct
-- PostgREST path. The grant is the actual control. RLS does not help here
-- either: RLS filters ROWS, it has no column dimension.
--
-- Fix: revoke the blanket table-level SELECT and re-grant SELECT column by
-- column, omitting last_error_message.
--
--   * last_error (timestamptz) is KEPT — the UI needs it to render a source as
--     unhealthy. Only last_error_message (the free text) is withheld.
--   * GRANT ALL ... TO service_role is left intact and re-asserted below: the
--     backend reads the message for logs, and db/supabase.py builds its client
--     with supabase_service_key, so /health/sources keeps working unchanged.
--
-- Idempotent / re-runnable: revoking a table-level privilege also drops the
-- matching column-level grants, so REVOKE-then-GRANT converges to the same
-- state on every run, from either the old or the new starting point.
--
-- NOTE for any future caller: with column-level (not table-level) SELECT,
-- `SELECT *` — i.e. PostgREST `?select=*` — fails with "permission denied for
-- table psx_data_source_health" for anon/authenticated. Columns must be named
-- explicitly. Nothing in frontend/ reads this table directly today (verified by
-- grep), so this breaks no current caller; it is the intended failure mode.

BEGIN;

-- Drop the blanket table-level SELECT. This also clears any column-level
-- SELECT previously granted to these roles, so the GRANT below is authoritative.
REVOKE SELECT ON TABLE public.psx_data_source_health FROM anon, authenticated;

-- Re-grant, column by column. last_error_message is deliberately absent.
-- Column list verified against the CREATE TABLE in
-- 20260716050000_data_source_health.sql (source, last_success, last_error,
-- last_error_message, rows_updated, refreshed_at).
GRANT SELECT (source, last_success, last_error, rows_updated, refreshed_at)
    ON public.psx_data_source_health TO anon, authenticated;

-- Unchanged; re-asserted so this file fully describes the table's grants.
GRANT ALL ON public.psx_data_source_health TO service_role;

COMMENT ON COLUMN public.psx_data_source_health.last_error_message IS
    'Raw str(e) from the failing job. May contain the Supabase project URL, '
    'table names and connection detail — service_role only, never granted to '
    'anon/authenticated. Public callers get last_error (the timestamp) instead.';

COMMIT;
