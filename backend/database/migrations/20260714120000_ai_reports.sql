-- AI Analysis & Reports — persistence (Phase 1).
-- Spec: docs/superpowers/specs/2026-07-14-ai-analysis-reports-design.md (§9, §19.5, §19.10)
--
-- ============================================================================
-- MUST BE RUN BY THE USER against Supabase (Dashboard SQL Editor or db push).
-- It is NOT applied automatically by the backend. Every statement is idempotent
-- (IF NOT EXISTS / guarded) so it is safe to re-run.
--
-- Report endpoints (a later wave) require this table live.
-- ============================================================================

-- ============ ai_reports ============
-- Stores the full structured (Pydantic-validated) report JSON. `content` also
-- carries an implicit `schema_version` inside the JSONB (no dedicated column) so
-- evolving report shapes stay backward-readable from cache (§19.10).
CREATE TABLE IF NOT EXISTS public.ai_reports (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       UUID NULL REFERENCES auth.users(id) ON DELETE CASCADE, -- NULL => shared
    report_type   TEXT NOT NULL
                  CHECK (report_type IN
                         ('market_brief', 'stock_analysis', 'portfolio',
                          'finance', 'dashboard_rec')),
    subject       TEXT NULL,          -- symbol for stock_analysis; NULL otherwise
    period_days   INT NULL,           -- portfolio valuation window
    trading_date  DATE NULL,          -- shared-cache key (market_brief / stock_analysis)
    content       JSONB NOT NULL,     -- full structured report (Pydantic-validated)
    context_hash  TEXT NOT NULL,      -- hash of the context bundle (cache invalidation)
    verified      BOOLEAN NOT NULL DEFAULT FALSE,
    provider      TEXT NULL,
    model         TEXT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_reports_user_type
    ON public.ai_reports (user_id, report_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_reports_subject
    ON public.ai_reports (report_type, subject, created_at DESC)
    WHERE user_id IS NULL;

-- §19.5 concurrency-safe get-or-create for shared reports: simultaneous requests
-- for the same (report_type, subject, trading_date) dedupe to a single row, so
-- there is no thundering herd of generations on the free tier.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_reports_shared_subject_date
    ON public.ai_reports (report_type, subject, trading_date)
    WHERE user_id IS NULL;

ALTER TABLE public.ai_reports ENABLE ROW LEVEL SECURITY;

-- Owner reads own reports; shared reports (user_id IS NULL) are public read.
DROP POLICY IF EXISTS "ai_reports_owner_select" ON public.ai_reports;
CREATE POLICY "ai_reports_owner_select" ON public.ai_reports
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "ai_reports_shared_select" ON public.ai_reports;
CREATE POLICY "ai_reports_shared_select" ON public.ai_reports
    FOR SELECT
    USING (user_id IS NULL);

-- All writes happen server-side via the service role; user_id always comes from
-- the verified JWT (never the client). No INSERT/UPDATE policy for authenticated.
GRANT SELECT ON public.ai_reports TO authenticated, anon;
GRANT ALL ON public.ai_reports TO service_role;

-- ============ ai_report_usage ============
-- Period-aware quota counter (day/week/month rollups derive from usage_date).
CREATE TABLE IF NOT EXISTS public.ai_report_usage (
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    usage_date   DATE NOT NULL,
    report_count INT NOT NULL DEFAULT 0,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, usage_date)
);

ALTER TABLE public.ai_report_usage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ai_report_usage_owner_select" ON public.ai_report_usage;
CREATE POLICY "ai_report_usage_owner_select" ON public.ai_report_usage
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

GRANT SELECT ON public.ai_report_usage TO authenticated;
GRANT ALL ON public.ai_report_usage TO service_role;
