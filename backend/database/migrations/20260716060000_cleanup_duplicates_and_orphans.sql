-- Cleanup: drop duplicate indexes and orphan rows discovered in the
-- July 16 audit.
-- Spec: (internal workstream plan)

-- NOTE: This migration includes two out-of-band repairs:
--   1. Drop psx_index_eod_unique — created outside the migration history in the
--      dev environment (probably via Supabase Dashboard). Not created by any
--      tracked migration, so whether it is a constraint or a bare index is
--      unknown from the repo; section 1 below branches on both and no-ops if
--      it is absent. Confirm with `\d psx_index_eod` before applying if you
--      want certainty about which branch will fire.
--   2. DROP INDEX IF EXISTS idx_psx_fund_nav_date  — created by
--      20260715010000 and superseded by 20260716020000 (which created
--      idx_psx_fund_nav_history_date). This DROP cleans up the older name.
-- Both are idempotent (IF EXISTS) and safe to re-run.

BEGIN;

-- 1. psx_index_eod: drop the redundant psx_index_eod_unique on (code, date).
--
--    Only TWO (code, date) uniqueness objects are accounted for by the tracked
--    migrations, not the "TRIPLE" this file's header claims:
--      a) the inline UNIQUE(code, date) in 20260706120000:113, which Postgres
--         auto-names psx_index_eod_code_date_key;
--      b) the PK psx_index_eod_pkey added by 20260714130000:23.
--    `psx_index_eod_unique` is created by no tracked migration, so it can only
--    be a hand-made Dashboard object. Its existence is UNVERIFIED from here —
--    if it does not exist, "triple" is wrong and this block is simply a no-op.
--    Either way (b) means dropping it loses no uniqueness guarantee.
--
--    This was previously `ALTER TABLE ... DROP CONSTRAINT IF EXISTS ... CASCADE`,
--    which could never match: Postgres would never name the inline constraint
--    `psx_index_eod_unique`, and if the object was hand-made via
--    CREATE UNIQUE INDEX it has no pg_constraint row at all, so DROP CONSTRAINT
--    IF EXISTS silently matched nothing. This file's own header (line 6) always
--    said DROP INDEX — the header was right and the statement was wrong.
--
--    We cannot inspect the live DB from here, so branch on what is actually
--    there rather than guessing: a plain DROP INDEX ERRORS ("cannot drop index
--    ... because constraint ... requires it") if the index turns out to be
--    constraint-owned, and DROP CONSTRAINT misses if it is a bare index.
--
--    CASCADE is deliberately NOT carried over. On a unique constraint it would
--    silently drop any FK that depends on (code, date). Nothing references it
--    today, but if something ever does we want the error, not a silent drop.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'psx_index_eod_unique'
          AND conrelid = 'public.psx_index_eod'::regclass
    ) THEN
        ALTER TABLE public.psx_index_eod DROP CONSTRAINT psx_index_eod_unique;
        RAISE NOTICE 'Dropped constraint psx_index_eod_unique.';
    ELSIF EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'psx_index_eod_unique'
          AND n.nspname = 'public'
          AND c.relkind = 'i'
    ) THEN
        EXECUTE 'DROP INDEX public.psx_index_eod_unique';
        RAISE NOTICE 'Dropped index psx_index_eod_unique.';
    ELSE
        RAISE NOTICE
            'No constraint or index named psx_index_eod_unique — nothing to drop. '
            '(Expected if it never existed outside the dev environment.)';
    END IF;
END $$;

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
