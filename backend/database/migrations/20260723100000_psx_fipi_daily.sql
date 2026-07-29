-- FIPI/LIPI daily investor flows (mirror of NCCPL data via finhisaab).
-- Upsert-by-natural-key: a re-scrape of the same day replaces that day's rows.

CREATE TABLE IF NOT EXISTS public.psx_fipi_daily (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trade_date   DATE NOT NULL,
    scope        TEXT NOT NULL,             -- MARKET | CLIENT_TYPE | SECTOR
    client_type  TEXT NOT NULL DEFAULT 'ALL',
    sector_code  TEXT NOT NULL DEFAULT 'ALL',
    sector_name  TEXT,
    market_type  TEXT NOT NULL DEFAULT 'ALL',
    buy_value_pkr    NUMERIC,
    sell_value_pkr   NUMERIC,
    net_value_pkr    NUMERIC,
    net_value_usd    NUMERIC,
    buy_volume       NUMERIC,
    sell_volume      NUMERIC,
    net_volume       NUMERIC,
    source       TEXT NOT NULL DEFAULT 'finhisaab',
    scraped_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (trade_date, scope, client_type, sector_code, market_type)
);
CREATE INDEX IF NOT EXISTS idx_fipi_daily_date ON public.psx_fipi_daily (trade_date DESC);
ALTER TABLE public.psx_fipi_daily ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "public read fipi" ON public.psx_fipi_daily;
CREATE POLICY "public read fipi" ON public.psx_fipi_daily FOR SELECT USING (true);
GRANT SELECT ON public.psx_fipi_daily TO anon, authenticated;
GRANT INSERT, UPDATE, SELECT, DELETE ON public.psx_fipi_daily TO service_role;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO service_role;
