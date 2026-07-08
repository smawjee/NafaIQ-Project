-- 20260710010000_index_ohlcv.sql
-- Add open/high/low columns to psx_index_eod to support candlestick rendering for indices (KSE-100, KSE-30, KMI-30, ALLSHR)

ALTER TABLE psx_index_eod
    ADD COLUMN IF NOT EXISTS open NUMERIC(12,2) DEFAULT 0 NOT NULL,
    ADD COLUMN IF NOT EXISTS high NUMERIC(12,2) DEFAULT 0 NOT NULL,
    ADD COLUMN IF NOT EXISTS low  NUMERIC(12,2) DEFAULT 0 NOT NULL;

-- Backfill open/high/low from close where missing (initial state)
UPDATE psx_index_eod
SET open = close, high = close, low = close
WHERE open = 0 AND high = 0 AND low = 0 AND close > 0;

CREATE INDEX IF NOT EXISTS idx_psx_index_eod_code_date
    ON psx_index_eod (code, date DESC);
