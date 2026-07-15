-- Cleanup: drop duplicate indexes and orphan rows discovered in the
-- July 16 audit.
-- Spec: (internal workstream plan)

BEGIN;

-- 1. psx_index_eod has TRIPLE unique constraint on (code, date):
--    PK already covers (code, date); psx_index_eod_unique is a duplicate.
ALTER TABLE psx_index_eod DROP CONSTRAINT IF EXISTS psx_index_eod_unique CASCADE;

-- 2. psx_fund_nav_history has two identical indexes on date DESC.
--    Keep idx_psx_fund_nav_history_date (the newer one); drop the original.
DROP INDEX IF EXISTS idx_psx_fund_nav_date;

-- 3. Delete orphan market_snapshot rows whose symbol is not in psx_profile.
DELETE FROM psx_market_snapshot ms
WHERE ms.symbol NOT IN (SELECT symbol FROM psx_profile);

-- 4. Fix OHLCV structural anomalies:
--    Set open = low where open < low (ensures open >= low)
UPDATE psx_ohlcv SET open = low WHERE open < low;
--    Set high = close where high < close (ensures high >= close)
UPDATE psx_ohlcv SET high = close WHERE high < close;

COMMIT;
