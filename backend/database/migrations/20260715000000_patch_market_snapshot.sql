-- Phase 0 / B1: AHL realtime upsert must not clobber DPS-derived columns.
--
-- The 5s job_poll_ahletrade writes only {price, volume, refreshed_at} for the
-- top-20 symbols. A Supabase upsert on the full row NULLs change, change_pct,
-- day_high, day_low â€” corrupting the sector aggregate every 5s. The fix is a
-- patch RPC that UPDATEs only the three AHL-owned columns.
--
-- Spec: (internal workstream plan)
--
-- ============================================================================
-- MUST BE RUN BY THE USER against Supabase (Dashboard SQL Editor or db push).
-- Idempotent (CREATE OR REPLACE), safe to re-run.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.patch_market_snapshot(rows jsonb)
RETURNS void
LANGUAGE sql
AS $$
    UPDATE public.psx_market_snapshot m
    SET
        price        = COALESCE((r->>'price')::numeric,        m.price),
        volume       = COALESCE((r->>'volume')::bigint,        m.volume),
        refreshed_at = COALESCE((r->>'refreshed_at')::timestamptz, m.refreshed_at)
    FROM jsonb_array_elements(rows) AS r
    WHERE m.symbol = r->>'symbol';
$$;

COMMENT ON FUNCTION public.patch_market_snapshot(jsonb) IS
    'Phase 0 B1: partial update of price/volume/refreshed_at from the AHL realtime feed without clobbering DPS-derived change/change_pct/day_high/day_low.';
