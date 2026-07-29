-- ai_reports.lang — make the report cache language-aware.
--
-- BUG: generate_report() takes `lang` and the model writes the report in that
-- language, but the cache key was (user_id, report_type, subject) with no lang
-- component, and the table had no lang column to key on. So the first caller of
-- the day fixed the language for everyone: an Urdu market_brief cached at 09:00
-- was served verbatim to every English reader until the next trading date, and
-- vice versa. Shared reports (user_id IS NULL) made this cross-user.
--
-- Existing rows are back-filled to 'en': every report generated before this
-- migration was cached under a lang-blind key, so their real language is not
-- recoverable from the row. 'en' matches the app default (web_app_origin's
-- default locale) and the worst case is one stale-language serve per key,
-- self-healing on the next trading date.
--
-- Idempotent: safe to re-run.

ALTER TABLE public.ai_reports
    ADD COLUMN IF NOT EXISTS lang TEXT NOT NULL DEFAULT 'en';

-- The lookup in reports_repo.get_latest_report filters on
-- (user_id, report_type, subject, lang) and orders by created_at DESC.
DROP INDEX IF EXISTS public.idx_ai_reports_user_type;
CREATE INDEX IF NOT EXISTS idx_ai_reports_user_type_lang
    ON public.ai_reports (user_id, report_type, lang, created_at DESC);

COMMENT ON COLUMN public.ai_reports.lang IS
    'Language the report content was generated in. Part of the cache key — a '
    'report must never be served to a reader who asked for another language.';
