-- Signals V4 foundation.
-- Raw market observations and published forecasts are append-only. The V4 API
-- never reads psx_ohlcv or psx_signals_v2 directly because those tables contain
-- legacy rows whose provenance and semantic meaning cannot be guaranteed.

BEGIN;

CREATE TABLE IF NOT EXISTS public.psx_ohlcv_raw (
    symbol              TEXT NOT NULL,
    date                DATE NOT NULL,
    source              TEXT NOT NULL,
    source_record_hash  TEXT NOT NULL,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    open                NUMERIC,
    high                NUMERIC,
    low                 NUMERIC,
    close               NUMERIC,
    volume              BIGINT,
    ldcp                NUMERIC,
    source_payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (symbol, date, source, source_record_hash)
);
CREATE INDEX IF NOT EXISTS idx_psx_ohlcv_raw_symbol_date
    ON public.psx_ohlcv_raw(symbol, date DESC);

CREATE TABLE IF NOT EXISTS public.psx_ohlcv_verified (
    symbol              TEXT NOT NULL,
    date                DATE NOT NULL,
    raw_source          TEXT NOT NULL,
    raw_record_hash     TEXT NOT NULL,
    open                NUMERIC,
    high                NUMERIC,
    low                 NUMERIC,
    close               NUMERIC,
    volume              BIGINT,
    ldcp                NUMERIC,
    verification_status TEXT NOT NULL DEFAULT 'VERIFIED',
    verification_version TEXT NOT NULL,
    verified_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, date),
    CONSTRAINT psx_ohlcv_verified_status_check
        CHECK (verification_status IN ('VERIFIED', 'EXCLUDED'))
);
CREATE INDEX IF NOT EXISTS idx_psx_ohlcv_verified_symbol_date
    ON public.psx_ohlcv_verified(symbol, date DESC);

CREATE TABLE IF NOT EXISTS public.psx_signal_events (
    event_id             TEXT PRIMARY KEY,
    symbol               TEXT NOT NULL,
    event_type           TEXT NOT NULL,
    title                TEXT NOT NULL DEFAULT '',
    published_at         TIMESTAMPTZ NOT NULL,
    period_end           DATE,
    source_url            TEXT,
    source_hash          TEXT,
    extraction_confidence NUMERIC,
    facts                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT psx_signal_events_confidence_check
        CHECK (extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1))
);
CREATE INDEX IF NOT EXISTS idx_psx_signal_events_symbol_time
    ON public.psx_signal_events(symbol, published_at DESC);

CREATE TABLE IF NOT EXISTS public.psx_signal_runs (
    run_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    as_of                DATE NOT NULL,
    model_version        TEXT NOT NULL,
    feature_version      TEXT NOT NULL,
    expected_count       INT NOT NULL DEFAULT 0,
    written_count        INT NOT NULL DEFAULT 0,
    status               TEXT NOT NULL DEFAULT 'STARTED',
    started_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at         TIMESTAMPTZ,
    CONSTRAINT psx_signal_runs_status_check
        CHECK (status IN ('STARTED', 'COMPLETE', 'FAILED'))
);

CREATE TABLE IF NOT EXISTS public.psx_signal_technical_daily (
    symbol               TEXT NOT NULL,
    as_of                DATE NOT NULL,
    bar_date             DATE NOT NULL,
    setup_status         TEXT NOT NULL,
    rating               TEXT,
    score                NUMERIC,
    bullish_count        INT NOT NULL DEFAULT 0,
    bearish_count        INT NOT NULL DEFAULT 0,
    neutral_count        INT NOT NULL DEFAULT 0,
    coverage             NUMERIC,
    components           JSONB NOT NULL DEFAULT '[]'::jsonb,
    reason_code           TEXT,
    version              TEXT NOT NULL,
    run_id               UUID REFERENCES public.psx_signal_runs(run_id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, as_of, version)
);

CREATE TABLE IF NOT EXISTS public.psx_signal_forecasts (
    forecast_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol               TEXT NOT NULL,
    event_id             TEXT REFERENCES public.psx_signal_events(event_id),
    issued_at             TIMESTAMPTZ NOT NULL,
    expires_at            TIMESTAMPTZ,
    horizon_sessions      INT NOT NULL DEFAULT 20,
    status                TEXT NOT NULL,
    direction             TEXT,
    p_outperform          NUMERIC,
    expected_excess_net   NUMERIC,
    interval_lower        NUMERIC,
    interval_upper        NUMERIC,
    abstain_reason        TEXT,
    model_version         TEXT NOT NULL,
    feature_version       TEXT NOT NULL,
    artifact_hash         TEXT,
    explanation_factors   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT psx_signal_forecasts_status_check
        CHECK (status IN ('PUBLISHED', 'SHADOW', 'ABSTAINED', 'STALE', 'UNAVAILABLE')),
    CONSTRAINT psx_signal_forecasts_direction_check
        CHECK (direction IS NULL OR direction IN ('OUTPERFORM', 'UNDERPERFORM')),
    CONSTRAINT psx_signal_forecasts_probability_check
        CHECK (p_outperform IS NULL OR (p_outperform >= 0 AND p_outperform <= 1))
);
CREATE INDEX IF NOT EXISTS idx_psx_signal_forecasts_symbol_time
    ON public.psx_signal_forecasts(symbol, issued_at DESC);

CREATE TABLE IF NOT EXISTS public.psx_signal_forecast_outcomes (
    forecast_id          UUID PRIMARY KEY REFERENCES public.psx_signal_forecasts(forecast_id),
    maturity_status      TEXT NOT NULL DEFAULT 'PENDING',
    realized_return      NUMERIC,
    benchmark_return     NUMERIC,
    excess_return_net    NUMERIC,
    evaluated_at         TIMESTAMPTZ,
    evaluation_version   TEXT,
    CONSTRAINT psx_signal_forecast_outcomes_status_check
        CHECK (maturity_status IN ('PENDING', 'MATURED', 'EVALUATED'))
);

ALTER TABLE public.psx_ohlcv_raw ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_ohlcv_verified ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_signal_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_signal_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_signal_technical_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_signal_forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_signal_forecast_outcomes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read verified signal data" ON public.psx_ohlcv_verified;
CREATE POLICY "Public read verified signal data" ON public.psx_ohlcv_verified FOR SELECT USING (true);
DROP POLICY IF EXISTS "Public read signal events" ON public.psx_signal_events;
CREATE POLICY "Public read signal events" ON public.psx_signal_events FOR SELECT USING (true);
DROP POLICY IF EXISTS "Public read technical setups" ON public.psx_signal_technical_daily;
CREATE POLICY "Public read technical setups" ON public.psx_signal_technical_daily FOR SELECT USING (true);
DROP POLICY IF EXISTS "Public read published forecasts" ON public.psx_signal_forecasts;
CREATE POLICY "Public read published forecasts" ON public.psx_signal_forecasts FOR SELECT USING (status = 'PUBLISHED');

GRANT SELECT ON public.psx_ohlcv_verified, public.psx_signal_events,
    public.psx_signal_technical_daily, public.psx_signal_forecasts,
    public.psx_signal_forecast_outcomes TO anon, authenticated;
GRANT SELECT, INSERT ON public.psx_ohlcv_raw, public.psx_signal_events,
    public.psx_signal_technical_daily, public.psx_signal_forecasts,
    public.psx_signal_forecast_outcomes TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.psx_ohlcv_verified, public.psx_signal_runs TO service_role;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260723100000_signals_v4_foundation.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
