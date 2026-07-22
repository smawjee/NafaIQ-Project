-- Finance integrity repairs (audit 2026-07-22 §2.2, §6).
--
-- 1. Resync every stored user_budgets.spent from real transactions. Nothing
--    refreshed this column on write, so 5 of 19 budgets were wrong — worst case
--    stored 0.00 against 54,500.00 of real spend. The alert engine read this
--    column, so two users sat ~50k over budget with no alert firing.
--    The application now resyncs on every transaction write; this is the
--    one-off correction of the accumulated drift.
--
-- 2. Pull the one future-dated transaction back to now(). A transaction cannot
--    have happened yet; this one was dated tomorrow and inflated the current
--    month's income.
--
-- 3. Add a CHECK preventing recurrence, with one day of slack for client clock
--    skew — matching services/finance/_common.not_in_future().
--
-- Touches only user_budgets and user_transactions. No market data
-- (psx_ohlcv, psx_index_eod, psx_market_snapshot, psx_profile) is read or
-- written, and nothing is deleted anywhere.
--
-- Idempotent: the resync is a pure recomputation, the date fix is bounded by a
-- WHERE, and the constraint is added only if absent.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Resync stored `spent`.
--    Mirrors BUDGET_SPENT_SQL in repositories/finance/budgets.py EXACTLY —
--    period-aware window, case/whitespace-insensitive category, stock trades
--    excluded. If you change one, change the other or they diverge again.
-- ---------------------------------------------------------------------------
UPDATE public.user_budgets b
SET spent = COALESCE((
        SELECT SUM(t.amount)
        FROM public.user_transactions t
        WHERE t.user_id = b.user_id
          AND t.transaction_type = 'expense'
          AND (t.source IS DISTINCT FROM 'stock_trade')
          AND lower(btrim(t.category)) = lower(btrim(b.category))
          AND t.transaction_date >= CASE lower(b.period)
                  WHEN 'weekly'    THEN date_trunc('week',    CURRENT_DATE)
                  WHEN 'quarterly' THEN date_trunc('quarter', CURRENT_DATE)
                  WHEN 'yearly'    THEN date_trunc('year',    CURRENT_DATE)
                  ELSE                  date_trunc('month',   CURRENT_DATE)
              END
          AND t.transaction_date <  CASE lower(b.period)
                  WHEN 'weekly'    THEN date_trunc('week',    CURRENT_DATE) + INTERVAL '1 week'
                  WHEN 'quarterly' THEN date_trunc('quarter', CURRENT_DATE) + INTERVAL '3 months'
                  WHEN 'yearly'    THEN date_trunc('year',    CURRENT_DATE) + INTERVAL '1 year'
                  ELSE                  date_trunc('month',   CURRENT_DATE) + INTERVAL '1 month'
              END
    ), 0);

-- ---------------------------------------------------------------------------
-- 2. Correct future-dated transactions.
--    Clamped to now() rather than deleted — the transaction itself is real, only
--    its timestamp is wrong, and deleting user financial records to fix a date
--    would destroy data.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    fixed bigint;
BEGIN
    WITH moved AS (
        UPDATE public.user_transactions
        SET transaction_date = now()
        WHERE transaction_date > now() + INTERVAL '1 day'
        RETURNING id
    )
    SELECT count(*) INTO fixed FROM moved;
    RAISE NOTICE 'Future-dated transactions corrected: %', fixed;
END $$;

-- ---------------------------------------------------------------------------
-- 3. Prevent recurrence.
--
--    A CHECK constraint CANNOT be used here: Postgres requires every function in
--    a CHECK to be IMMUTABLE, and now() is STABLE ("functions in check
--    constraint must be marked IMMUTABLE"). A BEFORE trigger is the correct
--    DB-level guard for a time-relative rule.
--
--    One day of slack absorbs client clock skew without accepting a mistyped
--    year. Kept in lockstep with services/finance/_common.not_in_future().
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.reject_future_transaction_date()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.transaction_date > now() + INTERVAL '1 day' THEN
        RAISE EXCEPTION
            'transaction_date cannot be in the future (got %)', NEW.transaction_date
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_user_transactions_not_future ON public.user_transactions;
CREATE TRIGGER trg_user_transactions_not_future
    BEFORE INSERT OR UPDATE OF transaction_date ON public.user_transactions
    FOR EACH ROW
    EXECUTE FUNCTION public.reject_future_transaction_date();

INSERT INTO public._applied_migrations (filename, applied_at)
VALUES ('20260722120000_finance_integrity.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
