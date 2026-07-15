-- Phase 0 / Workstream D: macro rates, mutual funds, news, filings, unusual
-- activity, and extended financials tables.
--
-- These tables back the new SBP / MUFAP / Business Recorder / financials.psx
-- scrapers and their corresponding public API endpoints. They are all created
-- idempotently so re-running this migration is safe.
--
-- Spec: (internal workstream plan)
-- ============================================================================
-- MUST BE RUN BY THE USER against Supabase (Dashboard SQL Editor or db push).
-- ============================================================================

-- ---------- Macro rates (KIBOR, PKRV, policy rate, FX) ----------

CREATE TABLE IF NOT EXISTS macro_rates (
    series text NOT NULL,
    date date NOT NULL,
    value numeric,
    refreshed_at timestamptz DEFAULT now(),
    PRIMARY KEY (series, date)
);

CREATE INDEX IF NOT EXISTS idx_macro_rates_date ON macro_rates(date DESC);

-- ---------- Mutual funds (MUFAP) ----------

CREATE TABLE IF NOT EXISTS psx_mutual_funds (
    fund_code text PRIMARY KEY,
    name text,
    category text,
    amc text,
    shariah boolean DEFAULT false,
    latest_nav numeric,
    nav_date date,
    aum numeric,
    refreshed_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS psx_fund_nav_history (
    fund_code text NOT NULL,
    date date NOT NULL,
    nav numeric,
    PRIMARY KEY (fund_code, date)
);

CREATE INDEX IF NOT EXISTS idx_psx_fund_nav_date ON psx_fund_nav_history(date DESC);

-- ---------- News (Business Recorder etc.) ----------

CREATE TABLE IF NOT EXISTS psx_news (
    id bigserial PRIMARY KEY,
    headline text NOT NULL,
    url text UNIQUE,
    source text,
    published_at timestamptz,
    tickers text[],
    body text,
    summary text,
    refreshed_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_psx_news_pub ON psx_news(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_psx_news_tickers ON psx_news USING gin(tickers);

-- ---------- Filings (PSX announcement PDFs) ----------

CREATE TABLE IF NOT EXISTS filings (
    announcement_id text PRIMARY KEY,
    symbol text,
    type text,
    filed_at date,
    pdf_url text,
    pdf_path text,
    text_content text,
    page_count int,
    refreshed_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_filings_symbol ON filings(symbol);
CREATE INDEX IF NOT EXISTS idx_filings_fts ON filings USING gin(to_tsvector('english', coalesce(text_content, '')));

-- ---------- Unusual activity (volume spikes) ----------

CREATE TABLE IF NOT EXISTS psx_unusual_activity (
    symbol text NOT NULL,
    ts timestamptz NOT NULL,
    price numeric,
    change_pct numeric,
    volume bigint,
    volume_ratio numeric,
    reason text,
    PRIMARY KEY (symbol, ts)
);

CREATE INDEX IF NOT EXISTS idx_psx_unusual_ts ON psx_unusual_activity(ts DESC);

-- ---------- Financials (annual + quarterly) ----------

CREATE TABLE IF NOT EXISTS psx_financials_annual (
    symbol text NOT NULL,
    year int NOT NULL,
    sales numeric,
    cogs numeric,
    gp numeric,
    op_income numeric,
    net_income numeric,
    eps numeric,
    total_assets numeric,
    total_equity numeric,
    total_debt numeric,
    current_assets numeric,
    current_liabilities numeric,
    gpm numeric,
    npm numeric,
    roe numeric,
    roa numeric,
    refreshed_at timestamptz DEFAULT now(),
    PRIMARY KEY (symbol, year)
);

CREATE TABLE IF NOT EXISTS psx_financials_quarterly (
    symbol text NOT NULL,
    period text NOT NULL,
    end_date date,
    sales numeric,
    net_income numeric,
    eps numeric,
    refreshed_at timestamptz DEFAULT now(),
    PRIMARY KEY (symbol, period)
);
