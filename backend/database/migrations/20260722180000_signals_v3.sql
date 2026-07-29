-- Signals V3.1 append-only persistence: scoring runs, daily signal rows, outcomes.
-- Signal rows are immutable: what the user saw is preserved forever. Maturity and
-- realized outcomes live in a separate insert-only table.

CREATE TABLE IF NOT EXISTS public.psx_signal_scoring_runs (
    scoring_run_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    as_of            DATE NOT NULL,
    model_version    TEXT NOT NULL,
    feature_version  TEXT NOT NULL,
    expected_symbol_count INT NOT NULL DEFAULT 0,
    written_symbol_count  INT NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'STARTED',   -- STARTED | COMPLETE | FAILED
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.psx_signals_v3_daily (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol           TEXT NOT NULL,
    as_of            DATE NOT NULL,
    horizon          TEXT NOT NULL,
    model_version    TEXT NOT NULL,
    feature_version  TEXT NOT NULL,
    calibration_version TEXT,
    universe_version TEXT,
    data_revision    INT NOT NULL DEFAULT 0,
    scoring_run_id   UUID NOT NULL REFERENCES public.psx_signal_scoring_runs(scoring_run_id),
    rank_score       NUMERIC,
    percentile       NUMERIC,
    p_beat_market    NUMERIC,
    p_positive_absolute NUMERIC,
    expected_excess_return NUMERIC,
    expected_absolute_return NUMERIC,
    signal           TEXT NOT NULL,
    sector           TEXT,
    data_quality_status TEXT,
    explanation_factors JSONB,
    artifact_hash    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, as_of, horizon, model_version, scoring_run_id)
);
CREATE INDEX IF NOT EXISTS idx_v3_daily_lookup ON public.psx_signals_v3_daily (symbol, horizon, as_of DESC);

CREATE TABLE IF NOT EXISTS public.psx_signal_outcomes (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signal_id        BIGINT NOT NULL REFERENCES public.psx_signals_v3_daily(id),
    maturity_status  TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING | MATURED | EVALUATED
    realized_return  NUMERIC,
    benchmark_return NUMERIC,
    excess_return    NUMERIC,
    large_loss       BOOLEAN,
    evaluated_at     TIMESTAMPTZ,
    evaluation_version TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_v3_outcomes_signal ON public.psx_signal_outcomes (signal_id);

ALTER TABLE public.psx_signals_v3_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_signal_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_signal_scoring_runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "public read v3 signals" ON public.psx_signals_v3_daily;
CREATE POLICY "public read v3 signals" ON public.psx_signals_v3_daily FOR SELECT USING (true);
DROP POLICY IF EXISTS "public read v3 outcomes" ON public.psx_signal_outcomes;
CREATE POLICY "public read v3 outcomes" ON public.psx_signal_outcomes FOR SELECT USING (true);
DROP POLICY IF EXISTS "public read v3 runs" ON public.psx_signal_scoring_runs;
CREATE POLICY "public read v3 runs" ON public.psx_signal_scoring_runs FOR SELECT USING (true);
GRANT SELECT ON public.psx_signals_v3_daily, public.psx_signal_outcomes, public.psx_signal_scoring_runs TO anon, authenticated;
-- service_role: INSERT only on signals/outcomes; runs may UPDATE status. No UPDATE/DELETE on signal rows.
GRANT INSERT, SELECT ON public.psx_signals_v3_daily, public.psx_signal_outcomes TO service_role;
GRANT INSERT, UPDATE, SELECT ON public.psx_signal_scoring_runs TO service_role;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO service_role;
-- Retention: prune scoring runs older than 400 days via a scheduled job (documented, not enforced here).
