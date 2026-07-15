-- Phase 0 / Workstream E: PSX OHLCV split-adjustment tracking + Shariah flag.
--
-- 1) psx_ohlcv gains three columns so we can correctly carry 10y of history
--    even when a stock had a split:
--      is_adjusted         — true when this bar has been adjusted for past splits
--      adjustment_factor   — cumulative split ratio (raw_price * factor == adjusted)
--      split_date          — date of the split that triggered the adjustment, if any
--    Newly written bars default to is_adjusted=true / factor=1.0 (i.e. "as fetched,
--    no further adjustment applied yet"). Split detection itself is a follow-up —
--    see the TODO comment near DPSScraper.fetch_payouts in scrapers/dps.py.
--
-- 2) psx_profile gains is_shariah so we can build Shariah-aware screeners.
--    The flag is derived in job_refresh_tv_data from the `listed_in` column
--    (a comma-separated list of index memberships) — if any of the KMI/MZNPI
--    Shariah indexes is present, the stock is Shariah-compliant.
--
-- Spec: (internal workstream plan)
--
-- ============================================================================
-- MUST BE RUN BY THE USER against Supabase (Dashboard SQL Editor or db push).
-- Idempotent (column / index guards), safe to re-run.
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='public' AND table_name='psx_ohlcv'
                   AND column_name='is_adjusted') THEN
        ALTER TABLE public.psx_ohlcv
            ADD COLUMN is_adjusted boolean DEFAULT true,
            ADD COLUMN adjustment_factor numeric DEFAULT 1.0,
            ADD COLUMN split_date date;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='public' AND table_name='psx_profile'
                   AND column_name='is_shariah') THEN
        ALTER TABLE public.psx_profile
            ADD COLUMN is_shariah boolean DEFAULT false;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_psx_ohlcv_split ON public.psx_ohlcv(symbol, split_date)
    WHERE split_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_psx_profile_shariah ON public.psx_profile(is_shariah)
    WHERE is_shariah = true;
