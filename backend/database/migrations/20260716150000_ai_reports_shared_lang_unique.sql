-- Keep shared AI report cache rows language-specific.
-- Without lang in this partial unique index, the first generated language wins
-- for market brief / stock analysis shared rows.

DROP INDEX IF EXISTS uq_ai_reports_shared_subject_date;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_reports_shared_subject_date_lang
ON ai_reports (report_type, subject, trading_date, lang)
WHERE user_id IS NULL;
