-- Cleanup: drop duplicate indexes and orphan rows discovered in the
-- July 16 audit.
-- Spec: (internal workstream plan)

-- NOTE: This migration includes two out-of-band repairs:
--   1. DROP INDEX IF EXISTS psx_index_eod_unique  — created outside the
--      migration history in the dev environment (probably via Supabase
--      Dashboard). Not created by any tracked migration.
--   2. DROP INDEX IF EXISTS idx_psx_fund_nav_date  — created by
--      20260715010000 and superseded by 20260716020000 (which created
--      idx_psx_fund_nav_history_date). This DROP cleans up the older name.
-- Both are idempotent (IF EXISTS) and safe to re-run.

BEGIN;

-- 1. psx_index_eod has TRIPLE unique constraint on (code, date):
--    PK already covers (code, date); psx_index_eod_unique is a duplicate.
ALTER TABLE psx_index_eod DROP CONSTRAINT IF EXISTS psx_index_eod_unique CASCADE;

-- 2. psx_fund_nav_history has two identical indexes on date DESC.
--    Keep idx_psx_fund_nav_history_date (the newer one); drop the original.
DROP INDEX IF EXISTS idx_psx_fund_nav_date;

-- 3. Delete orphan market_snapshot rows whose symbol is not in psx_profile.
--
--    GUARDED. psx_profile is repopulated by job_refresh_tv_data every 5 minutes.
--    Running this against an empty or partially-loaded psx_profile would delete
--    the ENTIRE snapshot table. The original used `NOT IN (SELECT symbol ...)`,
--    which additionally has the classic NULL trap: a single NULL symbol in
--    psx_profile makes the predicate never TRUE, so it silently deletes nothing.
--    NOT EXISTS is NULL-safe; the assertions below bound the blast radius.
DO $$
DECLARE
    profile_count  bigint;
    snapshot_count bigint;
    orphan_count   bigint;
BEGIN
    SELECT count(*) INTO profile_count  FROM psx_profile WHERE symbol IS NOT NULL;
    SELECT count(*) INTO snapshot_count FROM psx_market_snapshot;

    -- Refuse to run against a profile table that looks unloaded.
    IF profile_count < 100 THEN
        RAISE EXCEPTION
            'Refusing orphan cleanup: psx_profile has only % symbols (expected >= 100). '
            'It is probably mid-refresh or unloaded — rerun when populated.',
            profile_count;
    END IF;

    SELECT count(*) INTO orphan_count
    FROM psx_market_snapshot ms
    WHERE NOT EXISTS (
        SELECT 1 FROM psx_profile p WHERE p.symbol = ms.symbol
    );

    -- Refuse if this would remove an implausible share of the table.
    IF snapshot_count > 0 AND orphan_count > snapshot_count * 0.10 THEN
        -- NOTE: PL/pgSQL RAISE takes only `%` placeholders (no printf specs);
        -- round() here rather than trying to format inside the string.
        RAISE EXCEPTION
            'Refusing orphan cleanup: % of % snapshot rows (% percent) look orphaned, '
            'which exceeds the 10 percent safety threshold. Investigate before deleting.',
            orphan_count, snapshot_count,
            round(orphan_count::numeric / snapshot_count * 100, 1);
    END IF;

    DELETE FROM psx_market_snapshot ms
    WHERE NOT EXISTS (
        SELECT 1 FROM psx_profile p WHERE p.symbol = ms.symbol
    );

    RAISE NOTICE 'Orphan cleanup: deleted % of % snapshot rows.',
        orphan_count, snapshot_count;
END $$;

-- 4. OHLCV structural anomalies (open < low, high < close).
--
--    These UPDATEs REWRITE REAL MARKET DATA to mask a scraper bug. That is a
--    last resort, not a routine repair — the correct fix is at ingest, in the
--    scraper that produced the inconsistent bars. Every mutated row is copied
--    to psx_ohlcv_repair_audit first so the change is reviewable and
--    reversible; without that, the original values are gone forever.
--
--    NOTE: the original also under-covered — it handled open < low and
--    high < close but not high < open or low > close. Those are reported
--    below rather than silently rewritten.
CREATE TABLE IF NOT EXISTS psx_ohlcv_repair_audit (
    id          bigserial PRIMARY KEY,
    repaired_at timestamptz NOT NULL DEFAULT now(),
    migration   text        NOT NULL,
    symbol      text        NOT NULL,
    date        date        NOT NULL,
    reason      text        NOT NULL,
    old_open    numeric,
    old_high    numeric,
    old_low     numeric,
    old_close   numeric
);

ALTER TABLE psx_ohlcv_repair_audit ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON psx_ohlcv_repair_audit FROM anon, authenticated;

INSERT INTO psx_ohlcv_repair_audit (migration, symbol, date, reason, old_open, old_high, old_low, old_close)
SELECT '20260716060000', symbol, date, 'open < low', open, high, low, close
FROM psx_ohlcv WHERE open < low;

INSERT INTO psx_ohlcv_repair_audit (migration, symbol, date, reason, old_open, old_high, old_low, old_close)
SELECT '20260716060000', symbol, date, 'high < close', open, high, low, close
FROM psx_ohlcv WHERE high < close;

UPDATE psx_ohlcv SET open = low   WHERE open < low;
UPDATE psx_ohlcv SET high = close WHERE high < close;

-- Report (do not rewrite) the anomaly classes the original missed.
DO $$
DECLARE
    remaining bigint;
BEGIN
    SELECT count(*) INTO remaining
    FROM psx_ohlcv
    WHERE high < open OR low > close OR high < low;

    IF remaining > 0 THEN
        RAISE WARNING
            '% OHLCV rows still violate high >= open / low <= close / high >= low. '
            'These are NOT auto-repaired — fix the scraper at ingest.', remaining;
    END IF;
END $$;

COMMIT;
