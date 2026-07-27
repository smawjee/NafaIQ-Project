-- Live intraday index snapshot table.
--
-- The scheduler writes every 5 min during market hours (Mon-Fri 09:00–17:00 PKT)
-- by scraping the DPS homepage index carousel. The web API reads from this table
-- instead of scraping DPS in the request path, which failed silently on Railway
-- (timing out on the 95KB homepage) and fell back to stale yesterday-EOD data.
--
-- One row per benchmark index (KSE100, KMI30, ALLSHR, …), upserted on code.

BEGIN;

CREATE TABLE IF NOT EXISTS public.psx_index_live_snapshot (
    code       TEXT           NOT NULL PRIMARY KEY,
    date       DATE           NOT NULL DEFAULT CURRENT_DATE,
    close      NUMERIC(12, 2) NOT NULL,
    prev_close NUMERIC(12, 2),
    change     NUMERIC(12, 2),
    change_pct NUMERIC(12, 2),
    updated_at TIMESTAMPTZ    NOT NULL DEFAULT now()
);

COMMENT ON TABLE  public.psx_index_live_snapshot IS 'Intraday index snapshot refreshed every 5 min by scheduler';
COMMENT ON COLUMN public.psx_index_live_snapshot.code IS 'Index code e.g. KSE100, KMI30, ALLSHR';
COMMENT ON COLUMN public.psx_index_live_snapshot.date IS 'Trading date of the snapshot';

-- Same RLS policy as psx_index_eod: anon/authenticated can read, service_role writes.
ALTER TABLE public.psx_index_live_snapshot ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read index live snapshot"
    ON public.psx_index_live_snapshot
    FOR SELECT
    TO anon, authenticated
    USING (true);

GRANT SELECT ON public.psx_index_live_snapshot TO anon, authenticated;
GRANT ALL   ON public.psx_index_live_snapshot TO service_role;

COMMIT;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260724160000_create_index_live_snapshot.sql', now())
ON CONFLICT (filename) DO NOTHING;
