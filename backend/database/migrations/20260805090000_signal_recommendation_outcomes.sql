-- Live track record for the Tier 1 calibrated recommendations.
--
-- The calibration artifact already proves the probabilities hold on a 2025-2026
-- holdout the cells never saw. This pair of tables closes the remaining loop:
-- record what the engine actually told users, then measure what happened next.
--
-- Storage is the binding constraint on this project (no second Supabase
-- account), so the design is deliberately bounded:
--   * psx_signal_recommendations holds raw predictions, pruned to a 90-day
--     window after maturation -> ~600 symbols x 90 days = ~54k rows steady state.
--   * psx_signal_calibration_daily is the permanent record: one row per
--     (maturation date, horizon, probability bucket) = ~10 rows/day, ~0.5 MB/yr.
-- Never keep raw predictions indefinitely; the rollup is what survives.

BEGIN;

-- Raw point-in-time predictions, awaiting or holding their realised outcome.
CREATE TABLE IF NOT EXISTS public.psx_signal_recommendations (
    symbol              TEXT NOT NULL,
    as_of               DATE NOT NULL,
    horizon_sessions    INT  NOT NULL DEFAULT 20,
    rating              TEXT NOT NULL,
    p                   NUMERIC,
    p_lower             NUMERIC,
    p_upper             NUMERIC,
    -- p rounded to the nearest 0.05; the reliability diagram groups on this.
    prob_bucket         NUMERIC,
    -- Stored so maturation is a single price lookup rather than two.
    close_at_prediction NUMERIC,
    basis               TEXT,
    sample_size         INT NOT NULL DEFAULT 0,
    -- NULL until the horizon elapses and the outcome is measured.
    matured_on          DATE,
    realized_return     NUMERIC,
    outcome             BOOLEAN,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, as_of, horizon_sessions)
);

-- Maturation scans "everything old enough that is not yet matured".
CREATE INDEX IF NOT EXISTS idx_psx_signal_recommendations_pending
    ON public.psx_signal_recommendations(as_of)
    WHERE matured_on IS NULL;

-- The permanent, bounded reliability record.
CREATE TABLE IF NOT EXISTS public.psx_signal_calibration_daily (
    matured_on       DATE NOT NULL,
    horizon_sessions INT  NOT NULL,
    prob_bucket      NUMERIC NOT NULL,
    n                INT NOT NULL DEFAULT 0,
    hits             INT NOT NULL DEFAULT 0,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (matured_on, horizon_sessions, prob_bucket)
);
CREATE INDEX IF NOT EXISTS idx_psx_signal_calibration_recent
    ON public.psx_signal_calibration_daily(matured_on DESC);

ALTER TABLE public.psx_signal_recommendations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_signal_calibration_daily ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read signal recommendations" ON public.psx_signal_recommendations;
CREATE POLICY "Public read signal recommendations"
    ON public.psx_signal_recommendations FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public read signal calibration" ON public.psx_signal_calibration_daily;
CREATE POLICY "Public read signal calibration"
    ON public.psx_signal_calibration_daily FOR SELECT USING (true);

GRANT SELECT ON public.psx_signal_recommendations  TO anon, authenticated;
GRANT SELECT ON public.psx_signal_calibration_daily TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.psx_signal_recommendations  TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.psx_signal_calibration_daily TO service_role;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260805090000_signal_recommendation_outcomes.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
