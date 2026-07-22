-- Reconcile the CNERGY drift in portfolio 19 (audit 2026-07-22 §2.1).
--
-- State found: psx_holdings = 15 shares @ 110.00, but the only lot is
-- buy 5 @ 120.00. The stored aggregate is what the user sees and believes they
-- hold, so it is PRESERVED; the missing history is reconstructed instead.
--
-- An `adjust` lot is the fold's absolute snapshot, so recording 15 @ 110.00
-- AFTER the existing buy makes _fold_lots() reproduce the stored holding
-- exactly. The original buy lot is left intact as history — nothing is deleted.
--
-- Deliberately NOT the alternative: rebuilding psx_holdings from the lots would
-- change the user's position from 15 shares to 5 and destroy value they can see.
--
-- No finance reflection: reconstruction, not a cash movement.
-- Touches only stock_transactions (INSERT); reads psx_holdings / psx_portfolios.
-- No market data is read or written.
--
-- Guarded and idempotent. MUST BE RUN BY THE USER via the Supabase SQL Editor,
-- AFTER 20260722110000_backfill_holdings_opening_lots.sql.

BEGIN;

DO $$
DECLARE
    v_user_id   uuid;
    v_shares    bigint;
    v_avg_cost  numeric;
    v_lot_count bigint;
BEGIN
    SELECT p.user_id, h.shares, h.avg_cost
      INTO v_user_id, v_shares, v_avg_cost
    FROM public.psx_holdings h
    JOIN public.psx_portfolios p ON p.id = h.portfolio_id
    WHERE h.portfolio_id = 19 AND h.symbol = 'CNERGY';

    IF v_user_id IS NULL THEN
        RAISE NOTICE 'No CNERGY holding in portfolio 19 — nothing to reconcile.';
        RETURN;
    END IF;

    -- Refuse if the position no longer matches what the audit observed.
    IF v_shares <> 15 OR v_avg_cost <> 110.00 THEN
        RAISE EXCEPTION
            'CNERGY holding is now % shares @ % (audit saw 15 @ 110.00). '
            'Data moved since 2026-07-22 — re-run '
            'scripts.portfolio.reconciliation_report and rewrite this migration '
            'before applying.', v_shares, v_avg_cost;
    END IF;

    -- Idempotency: skip if a reconciling adjust lot is already present.
    SELECT count(*) INTO v_lot_count
    FROM public.stock_transactions
    WHERE portfolio_id = 19 AND symbol = 'CNERGY' AND side = 'adjust';

    IF v_lot_count > 0 THEN
        RAISE NOTICE 'CNERGY already has an adjust lot — nothing to do.';
        RETURN;
    END IF;

    INSERT INTO public.stock_transactions
        (user_id, portfolio_id, symbol, side, quantity, price, fees,
         executed_at, notes, source)
    VALUES
        (v_user_id, 19, 'CNERGY', 'adjust', v_shares, v_avg_cost, 0,
         now(), 'Drift reconciliation (audit 2026-07-22)', 'import');

    RAISE NOTICE 'CNERGY reconciled: adjust lot % @ %.', v_shares, v_avg_cost;
END $$;

INSERT INTO public._applied_migrations (filename, applied_at)
VALUES ('20260722110100_reconcile_cnergy_drift.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
