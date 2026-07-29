-- Restore NULLS NOT DISTINCT on the shared-report unique index, and purge the
-- duplicate/fixture rows it should have prevented.
--
-- REGRESSION. 20260714140000_ai_reports_shared_unique_nulls.sql created this
-- index WITH `NULLS NOT DISTINCT`, and its comment spells out exactly why:
-- market_brief has `subject = NULL`, Postgres treats NULLs as DISTINCT by
-- default, so without that clause every NULL-subject row is unique to the index
-- and `ON CONFLICT ... DO NOTHING` in reports_repo.get_or_create_shared never
-- fires. 20260716150000_ai_reports_shared_lang_unique.sql then re-keyed the
-- index to add `lang` — and dropped the clause on the way through, silently
-- reverting the fix.
--
-- Live effect (observed 2026-07-16): three "unique" shared market_brief rows
-- for the same (report_type, subject=NULL, trading_date, lang).
-- get_latest_report does ORDER BY created_at DESC LIMIT 1, so the NEWEST
-- wins — which is how a stale row shadowed the real 10:19:49 brief and got
-- served to every user all day.
--
-- FIX (2026-07-16 2nd pass): the index name *on the live DB* was still
-- `uq_ai_reports_shared_subject_date` (the pre-20260716150000 name) because
-- 20260716150000 was never applied there. The previous version of this file
-- only dropped the `_lang` variant, so the old index persisted and step 3's
-- CREATE silently failed on a name collision. This version drops BOTH names
-- to cover whatever state the live DB is in.
--
-- MUST BE RUN BY THE USER against Supabase. Idempotent.

-- 0. Ensure the `lang` column exists — needed for the DELETE below and for
--    the new index. Back-fill NULL rows to 'en' so the unique index can fire.
ALTER TABLE public.ai_reports
    ADD COLUMN IF NOT EXISTS lang TEXT NOT NULL DEFAULT 'en';
UPDATE public.ai_reports SET lang = 'en' WHERE lang IS NULL;

-- 1. Collapse existing duplicates, keeping the OLDEST row per key.
--    Oldest, not newest: the first row of the day is the one the scheduler
--    generated from that morning's real bundle; anything later for the same
--    key only exists because the index wasn't enforcing.
--
--    Uses ctid (physical row pointer) instead of (created_at, id) tuple
--    comparison — ctid is always unique and avoids edge cases where two
--    rows have identical created_at timestamps.
DELETE FROM public.ai_reports a
USING public.ai_reports b
WHERE a.user_id IS NULL
  AND b.user_id IS NULL
  AND a.report_type = b.report_type
  AND a.trading_date = b.trading_date
  AND a.lang = b.lang
  AND a.subject IS NOT DISTINCT FROM b.subject
  AND a.ctid > b.ctid;

-- 2. Drop ANY variant of the shared unique index — the DB may have the old
--    name (uq_ai_reports_shared_subject_date), the lang-keyed name
--    (_date_lang), both, or neither. Each DROP is idempotent.
DROP INDEX IF EXISTS public.uq_ai_reports_shared_subject_date;
DROP INDEX IF EXISTS public.uq_ai_reports_shared_subject_date_lang;

-- 3. Recreate the index with the clause that makes NULL subjects collide.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_reports_shared_subject_date_lang
    ON public.ai_reports (report_type, subject, trading_date, lang)
    NULLS NOT DISTINCT
    WHERE user_id IS NULL;
