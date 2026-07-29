-- Daily cross-sectional factor ranks for the liquid PSX universe.
-- Precomputed by a scheduler job; the signal API reads one row per symbol.
-- Descriptive only (percentile ranks vs peers) — never a forecast.

BEGIN;

CREATE TABLE IF NOT EXISTS public.psx_signal_cross_section (
    symbol               TEXT NOT NULL,
    as_of                DATE NOT NULL,
    composite_percentile NUMERIC,
    universe_size        INT NOT NULL DEFAULT 0,
    factors              JSONB NOT NULL DEFAULT '{}'::jsonb,
    computed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol)
);
CREATE INDEX IF NOT EXISTS idx_psx_signal_cross_section_rank
    ON public.psx_signal_cross_section(composite_percentile DESC);

ALTER TABLE public.psx_signal_cross_section ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read cross section" ON public.psx_signal_cross_section;
CREATE POLICY "Public read cross section" ON public.psx_signal_cross_section FOR SELECT USING (true);
GRANT SELECT ON public.psx_signal_cross_section TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.psx_signal_cross_section TO service_role;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260724120000_signals_v4_cross_section.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
