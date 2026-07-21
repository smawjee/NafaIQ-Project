-- Backfill synthetic opening lots for holdings that have no stock_transactions.
--
-- Audit 2026-07-22 §2.1: 4 holdings across portfolios 2 and 6 have no backing
-- lots (ENGRO/HBL/OGDC in pf 2, HBL in pf 6). Product rule: a holding exists
-- because a transaction happened, so these are real purchases whose receipt was
-- never written. Reconstruct the receipt; never delete the position.
--
-- Side is `adjust` — the fold's absolute snapshot (shares = quantity,
-- avg_cost = price) — so rebuild_holdings_from_transactions() reproduces each
-- holding exactly. Nothing a user currently sees changes: the holding's shares
-- and avg_cost are read, not written. source='import' marks these lots as
-- reconstructed rather than user-entered.
--
-- NO user_transactions reflection is created: this restores past state, it is
-- not a new cash movement. Creating one would inflate the user's spending.
--
-- Touches only stock_transactions (INSERT) and reads psx_holdings /
-- psx_portfolios. No market data (psx_ohlcv, psx_market_snapshot, psx_profile,
-- psx_index_eod) is read or written.
--
-- Idempotent: the NOT EXISTS guard skips any holding that already has lots.
-- MUST BE RUN BY THE USER via the Supabase Dashboard SQL Editor.
--
-- Supersedes the untracked backend/database/backfill_holdings_opening_lots.sql,
-- which was never applied because it sat outside migrations/.

BEGIN;

INSERT INTO public.stock_transactions
    (user_id, portfolio_id, symbol, side, quantity, price, fees,
     executed_at, notes, source)
SELECT
    p.user_id,
    h.portfolio_id,
    h.symbol,
    'adjust',
    h.shares,
    h.avg_cost,
    0,
    COALESCE(h.purchased_at::timestamptz, now()),
    'Synthetic opening lot (audit 2026-07-22 backfill)',
    'import'
FROM public.psx_holdings h
JOIN public.psx_portfolios p ON p.id = h.portfolio_id
WHERE p.user_id IS NOT NULL       -- skip ownerless legacy rows
  AND h.shares > 0                -- respect CHECK (quantity > 0)
  AND NOT EXISTS (
      SELECT 1 FROM public.stock_transactions t
      WHERE t.portfolio_id = h.portfolio_id
        AND t.symbol = h.symbol
  );

-- Verification: must return 0.
DO $$
DECLARE
    remaining bigint;
BEGIN
    SELECT count(*) INTO remaining
    FROM public.psx_holdings h
    JOIN public.psx_portfolios p ON p.id = h.portfolio_id
    WHERE p.user_id IS NOT NULL AND h.shares > 0
      AND NOT EXISTS (
          SELECT 1 FROM public.stock_transactions t
          WHERE t.portfolio_id = h.portfolio_id AND t.symbol = h.symbol
      );
    IF remaining > 0 THEN
        RAISE EXCEPTION 'Backfill incomplete: % holdings still have no lots.', remaining;
    END IF;
    RAISE NOTICE 'Opening-lot backfill complete: every holding now has lots.';
END $$;

INSERT INTO public._applied_migrations (filename, applied_at)
VALUES ('20260722110000_backfill_holdings_opening_lots.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
