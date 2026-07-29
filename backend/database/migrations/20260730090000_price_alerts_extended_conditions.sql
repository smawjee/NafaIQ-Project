-- ============================================================================
-- price_alerts: allow the four new alert conditions
--
-- The original DDL (20260706130000_psx_realtime_and_fix.sql) pinned `condition`
-- to a CHECK over exactly four values:
--
--     CHECK (condition IN ('above','below','cross_above','cross_below'))
--
-- so the database itself rejects anything richer, no matter what the API
-- validates. This widens it to cover the new types:
--
--     pct_change_above / pct_change_below  -- day move >= / <= N percent
--     volume_spike                         -- volume >= N x average volume
--     high_52w / low_52w                   -- new 52-week high / low
--
-- On the `price` column: it stays the threshold for ALL conditions, and its
-- meaning now depends on `condition` — PKR for above/below/cross_*, percent for
-- pct_change_*, a multiple for volume_spike, and unused (0) for the 52-week
-- conditions, which have no threshold. Renaming it to `threshold` would be
-- clearer but would break every existing reader (repositories, schemas, the
-- assistant tool, the web and mobile clients) for no functional gain.
-- NUMERIC(14,2) holds all four shapes comfortably.
--
-- Re-runnable: the constraint is dropped IF EXISTS before being re-added, and
-- the whole thing runs in one transaction so a failure cannot leave the table
-- unconstrained.
-- ============================================================================

BEGIN;

ALTER TABLE public.price_alerts
    DROP CONSTRAINT IF EXISTS price_alerts_condition_check;

ALTER TABLE public.price_alerts
    ADD CONSTRAINT price_alerts_condition_check
    CHECK (condition IN (
        'above',
        'below',
        'cross_above',
        'cross_below',
        'pct_change_above',
        'pct_change_below',
        'volume_spike',
        'high_52w',
        'low_52w'
    ));

-- The threshold rule has to become condition-aware too.
--
-- `price_alerts_price_positive` (20260711000600) enforced a flat `price > 0`.
-- That was right when every condition was a rupee level, but it makes the
-- 52-week conditions — which have NO threshold — impossible to insert: the API
-- normalises their `price` to 0 and Postgres rejects the row. Found by actually
-- inserting one rather than by reading the schema.
--
-- Replacing it with a paired rule is STRICTER than what it replaces, not looser:
-- it pins price = 0 for the threshold-less conditions (so a stray value can't be
-- stored and later rendered as if it meant something) while still demanding a
-- positive threshold everywhere else.
ALTER TABLE public.price_alerts
    DROP CONSTRAINT IF EXISTS price_alerts_price_positive;

ALTER TABLE public.price_alerts
    ADD CONSTRAINT price_alerts_price_positive
    CHECK (
        CASE
            WHEN condition IN ('high_52w', 'low_52w') THEN price = 0
            ELSE price > 0
        END
    );

-- No new index needed: the evaluator's 52-week / average-volume scan is served
-- by the existing `idx_psx_ohlcv_symbol_date_desc` on (symbol, date DESC),
-- added in 20260712110000_performance_indexes.sql. A second index over the same
-- columns would only cost disk and write throughput on a ~990k-row table.

-- ---------------------------------------------------------------------------
-- Migration ledger
-- ---------------------------------------------------------------------------
INSERT INTO public._applied_migrations (filename) VALUES
    ('20260730090000_price_alerts_extended_conditions.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
