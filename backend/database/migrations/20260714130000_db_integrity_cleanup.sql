-- DB integrity cleanup (low-risk) — companion to Phase 0 of the AI reports spec.
-- Spec: docs/superpowers/specs/2026-07-14-ai-analysis-reports-design.md (§17)
--
-- ============================================================================
-- MUST BE RUN BY THE USER against Supabase (Dashboard SQL Editor or db push).
-- It is NOT applied automatically by the backend and NOT covered by CI.
-- Every statement is idempotent (IF EXISTS / guarded DO blocks) so it is safe
-- to re-run. The NOT NULL section is intentionally guarded — read its comments
-- and run the pre-check SELECTs FIRST; it will fail if legacy NULL rows exist.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. psx_index_eod: add a PRIMARY KEY (currently only UNIQUE(code, date)).
--    code/date are already NOT NULL, so promoting them to PK is safe.
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.psx_index_eod'::regclass AND contype = 'p'
    ) THEN
        ALTER TABLE public.psx_index_eod
            ADD CONSTRAINT psx_index_eod_pkey PRIMARY KEY (code, date);
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2. psx_signals: drop the redundant UNIQUE(symbol) — symbol is already the PK,
--    so the extra unique constraint/index is pure duplication.
-- ----------------------------------------------------------------------------
ALTER TABLE public.psx_signals DROP CONSTRAINT IF EXISTS psx_signals_symbol_key;

-- ----------------------------------------------------------------------------
-- 3. Drop duplicate / overlapping indexes (keep the more useful of each pair).
--    Verified against the migrations before dropping.
-- ----------------------------------------------------------------------------
-- psx_ohlcv(symbol, date) [asc] vs (symbol, date DESC): keep the DESC index,
-- which serves the ORDER BY date DESC / DISTINCT ON reads in valuation.py.
DROP INDEX IF EXISTS public.idx_psx_ohlcv_sym_date;            -- keep idx_psx_ohlcv_symbol_date_desc

-- psx_market_snapshot(symbol): two identical indexes; keep the descriptive one.
DROP INDEX IF EXISTS public.idx_psx_ms_sym;                    -- keep idx_psx_market_snapshot_symbol

-- psx_index_eod(code, date) [asc] vs (code, date DESC): keep the DESC index.
DROP INDEX IF EXISTS public.idx_psx_idx_code;                  -- keep idx_psx_index_eod_code_date

-- stock_transactions(user_id, executed_at DESC): two identical indexes; keep
-- the descriptive one.
DROP INDEX IF EXISTS public.idx_stock_tx_user_date;            -- keep idx_stock_transactions_user_id_executed_at

-- NOTE on idx_user_watchlist_user: §17 lists it as "duplicated", but both
-- migrations declare the SAME index name with CREATE INDEX IF NOT EXISTS, so
-- only ONE physical index exists on user_watchlist(user_id). Nothing to drop —
-- dropping it would remove a useful, non-duplicated index. Left in place.

-- ----------------------------------------------------------------------------
-- 4. NOT NULL tightening on v1 PSX owner columns.
--    !!! GUARDED — RUN THE PRE-CHECK SELECTS BELOW FIRST. !!!
--    These ALTERs WILL FAIL if any legacy row has a NULL owner. That failure is
--    intentional (it surfaces orphaned rows); do not force past it — clean or
--    delete the offending rows first, then re-run.
--
--    Pre-check (run these; every count must be 0 before uncommenting the ALTERs):
--        SELECT count(*) FROM public.psx_portfolios WHERE user_id     IS NULL;
--        SELECT count(*) FROM public.psx_holdings   WHERE portfolio_id IS NULL;
--        SELECT count(*) FROM public.psx_watchlist  WHERE user_id     IS NULL;
--        SELECT count(*) FROM public.psx_alerts     WHERE user_id     IS NULL;
-- ----------------------------------------------------------------------------
-- ALTER TABLE public.psx_portfolios ALTER COLUMN user_id      SET NOT NULL;
-- ALTER TABLE public.psx_holdings   ALTER COLUMN portfolio_id SET NOT NULL;
-- ALTER TABLE public.psx_watchlist  ALTER COLUMN user_id      SET NOT NULL;
-- ALTER TABLE public.psx_alerts     ALTER COLUMN user_id      SET NOT NULL;

-- ----------------------------------------------------------------------------
-- 5. Deliberately NOT done: a hard symbol-master FK. App-level
--    require_known_symbol stays the guard — a scraped psx_profile cache can lag
--    newly listed tickers, and a hard FK would reject valid new symbols. See §17.
-- ----------------------------------------------------------------------------
