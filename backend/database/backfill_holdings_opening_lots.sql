-- Backfill: synthetic opening lots for holdings that predate the unified write path.
-- Spec: docs/superpowers/specs/2026-07-14-ai-analysis-reports-design.md (§2.5 item 7)
--
-- ============================================================================
-- MUST BE RUN BY THE USER against Supabase (Dashboard SQL Editor / db push).
-- It is NOT applied automatically by the backend and NOT covered by CI.
-- Run it ONCE, AFTER deploying the Phase 0 code, so that every existing
-- psx_holdings row has a backing stock_transactions lot and history is complete
-- before reports read it.
-- ============================================================================
--
-- Semantics: for each psx_holdings row that has NO stock_transactions lot for
-- its (portfolio_id, symbol), insert one synthetic OPENING `adjust` lot with
-- source='import'. `adjust` is the fold's absolute snapshot (shares = quantity,
-- avg_cost = price), so rebuild_holdings_from_transactions() reproduces the
-- holding exactly. No user_transactions finance reflection is created — this is
-- a reconstruction of past state, not a new cash movement.
--
-- Idempotent: re-running is a no-op because the NOT EXISTS guard skips any
-- holding that already has lots.

-- ---- Pre-check: how many holdings are currently un-backed? (optional) ----
--     SELECT count(*)
--     FROM public.psx_holdings h
--     JOIN public.psx_portfolios p ON p.id = h.portfolio_id
--     WHERE p.user_id IS NOT NULL
--       AND h.shares > 0
--       AND NOT EXISTS (
--           SELECT 1 FROM public.stock_transactions t
--           WHERE t.portfolio_id = h.portfolio_id AND t.symbol = h.symbol
--       );

INSERT INTO public.stock_transactions
    (user_id, portfolio_id, symbol, side, quantity, price, fees,
     executed_at, notes, source)
SELECT
    p.user_id,
    h.portfolio_id,
    h.symbol,
    'adjust'                                              AS side,
    h.shares                                              AS quantity,
    h.avg_cost                                            AS price,
    0                                                     AS fees,
    COALESCE(h.purchased_at::timestamptz, now())          AS executed_at,
    'Synthetic opening lot (backfill)'                    AS notes,
    'import'                                              AS source
FROM public.psx_holdings h
JOIN public.psx_portfolios p ON p.id = h.portfolio_id
WHERE p.user_id IS NOT NULL      -- skip orphaned/legacy rows with no owner
  AND h.shares > 0               -- respect the CHECK (quantity > 0)
  AND NOT EXISTS (
      SELECT 1 FROM public.stock_transactions t
      WHERE t.portfolio_id = h.portfolio_id
        AND t.symbol = h.symbol
  );

-- ---- Post-check: should return 0 rows after the backfill ----
--     SELECT h.portfolio_id, h.symbol
--     FROM public.psx_holdings h
--     JOIN public.psx_portfolios p ON p.id = h.portfolio_id
--     WHERE p.user_id IS NOT NULL AND h.shares > 0
--       AND NOT EXISTS (
--           SELECT 1 FROM public.stock_transactions t
--           WHERE t.portfolio_id = h.portfolio_id AND t.symbol = h.symbol
--       );
