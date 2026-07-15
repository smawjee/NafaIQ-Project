-- Phase 0 / Workstream D follow-up:
-- Add RLS + public read grants to the 8 new tables so they match the project
-- convention (public market data is RLS-on + read-by-anyone; user data is
-- RLS-on + per-user). Also adds two missing DESC indexes for the financials
-- tables so /api/financials/{symbol}/annual and /quarterly are not forced
-- to sequential-scan once data arrives.
--
-- ============================================================================
-- MUST BE RUN BY THE USER against Supabase. Idempotent (uses DO $$ guards
-- so policies/grant are not created twice).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. RLS + public read policy + grants for the 8 new tables.
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'macro_rates',
        'psx_mutual_funds',
        'psx_fund_nav_history',
        'psx_news',
        'filings',
        'psx_unusual_activity',
        'psx_financials_annual',
        'psx_financials_quarterly'
    ]
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON public.%I',
            'Public read ' || t, t
        );
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT USING (true)',
            'Public read ' || t, t
        );
        EXECUTE format('GRANT SELECT ON public.%I TO anon, authenticated', t);
        EXECUTE format('GRANT ALL    ON public.%I TO service_role', t);
    END LOOP;
END $$;

-- ----------------------------------------------------------------------------
-- 2. DESC indexes on the financials tables (year/period desc per symbol).
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_psx_fa_sym_year
    ON public.psx_financials_annual(symbol, year DESC);
CREATE INDEX IF NOT EXISTS idx_psx_fq_sym_period
    ON public.psx_financials_quarterly(symbol, period DESC);

-- ----------------------------------------------------------------------------
-- 3. (Optional but cheap) Tighten new columns to NOT NULL now that every
--    existing row has a non-null default. Prevents future scrapers from
--    accidentally writing NULLs.
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'psx_ohlcv'
          AND column_name = 'is_adjusted' AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE public.psx_ohlcv
            ALTER COLUMN is_adjusted SET NOT NULL,
            ALTER COLUMN adjustment_factor SET NOT NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'psx_profile'
          AND column_name = 'is_shariah' AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE public.psx_profile
            ALTER COLUMN is_shariah SET NOT NULL;
    END IF;
END $$;
