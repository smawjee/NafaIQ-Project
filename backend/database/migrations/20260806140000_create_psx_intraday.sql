-- 5-minute intraday OHLCV bars for PSX equities.
--
-- WHY THIS TABLE EXISTS
-- Nothing in the system retained an intraday tick series. `psx_market_snapshot`
-- and `psx_index_live_snapshot` are both upsert-on-key — one row per
-- symbol/code, overwritten on every refresh — so the only queryable price
-- history was `psx_ohlcv`, which holds one bar per DAY. The chart's "1D"
-- timeframe therefore had nothing intraday to draw and silently rendered five
-- daily candles instead.
--
-- HOW IT IS WRITTEN
-- `job_capture_intraday` samples `psx_market_snapshot` every minute during
-- market hours and folds each sample into the current 5-minute bucket: the
-- first sample of a bucket sets `open`, later ones widen `high`/`low` and move
-- `close`. One row per (symbol, bucket), upserted — so a re-run of the same
-- minute is a no-op rather than a duplicate.
--
-- `cum_volume` is the DAY-CUMULATIVE figure the snapshot reports, not per-bar
-- volume. Storing it raw is what keeps the writer idempotent; the read path
-- diffs consecutive buckets within a session to derive per-bar volume.
--
-- RETENTION
-- ~500 symbols x 78 buckets/session is ~39k rows per trading day, so this table
-- is pruned nightly by `job_prune_intraday`. It backs a chart window, not an
-- archive — `psx_ohlcv` remains the historical record.

BEGIN;

CREATE TABLE IF NOT EXISTS public.psx_intraday (
    symbol       TEXT           NOT NULL,
    -- Start of the 5-minute bucket, UTC. PSX trades 09:30-15:30 PKT (UTC+5).
    ts           TIMESTAMPTZ    NOT NULL,
    -- PKT trading date. Written by the job rather than generated: Postgres
    -- rejects `ts AT TIME ZONE 'Asia/Karachi'` in a generated column because
    -- that expression is STABLE, not IMMUTABLE.
    session_date DATE           NOT NULL,
    open         NUMERIC(14, 4) NOT NULL,
    high         NUMERIC(14, 4) NOT NULL,
    low          NUMERIC(14, 4) NOT NULL,
    close        NUMERIC(14, 4) NOT NULL,
    cum_volume   BIGINT         NOT NULL DEFAULT 0,
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, ts)
);

COMMENT ON TABLE  public.psx_intraday IS '5-minute intraday bars, sampled from psx_market_snapshot during market hours; pruned nightly';
COMMENT ON COLUMN public.psx_intraday.ts IS 'Start of the 5-minute bucket (UTC)';
COMMENT ON COLUMN public.psx_intraday.session_date IS 'PKT trading date this bucket belongs to';
COMMENT ON COLUMN public.psx_intraday.cum_volume IS 'Day-cumulative volume as reported; per-bar volume is derived by diffing buckets';

-- The chart read: one symbol, newest session first.
CREATE INDEX IF NOT EXISTS idx_psx_intraday_symbol_ts
    ON public.psx_intraday (symbol, ts DESC);

-- The nightly prune, and the writer's "rows in the current bucket" read.
CREATE INDEX IF NOT EXISTS idx_psx_intraday_session_date
    ON public.psx_intraday (session_date);

-- Same policy as psx_index_live_snapshot: anon/authenticated read, service_role writes.
ALTER TABLE public.psx_intraday ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read intraday" ON public.psx_intraday;
CREATE POLICY "Public read intraday"
    ON public.psx_intraday
    FOR SELECT
    TO anon, authenticated
    USING (true);

GRANT SELECT ON public.psx_intraday TO anon, authenticated;
GRANT ALL    ON public.psx_intraday TO service_role;

COMMIT;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260806140000_create_psx_intraday.sql', now())
ON CONFLICT (filename) DO NOTHING;
