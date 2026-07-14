-- Fix F1 (audit 2026-07-14): the shared-report unique index must treat NULL
-- `subject` rows as EQUAL, or market_brief (which has subject = NULL) is never
-- deduped and concurrent generations insert duplicate rows.
--
-- Postgres default treats NULLs as DISTINCT in a unique index, so
-- `ON CONFLICT (report_type, subject, trading_date) DO NOTHING` never fires for
-- market_brief. `NULLS NOT DISTINCT` (Postgres 15+, which Supabase runs) makes
-- the two NULL-subject rows collide, restoring the §19.5 single-generation
-- guarantee for the daily market brief.
--
-- MUST BE RUN BY THE USER against Supabase. Idempotent.

DROP INDEX IF EXISTS public.uq_ai_reports_shared_subject_date;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_reports_shared_subject_date
    ON public.ai_reports (report_type, subject, trading_date)
    NULLS NOT DISTINCT
    WHERE user_id IS NULL;
