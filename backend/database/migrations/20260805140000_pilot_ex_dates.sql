-- Pilot ex-date attribution (2026-08-05 measurement-fix, part F1).
--
-- ADDITIVE ONLY. Adds three columns to psx_corporate_actions (a pilot table
-- created by 20260805120000); no existing row is altered, nothing else is
-- touched.
--
-- Why (per the diagnosis in
-- .opencode/plans/2026-08-05-signals-pilot-measurement-fix.md, findings
-- D1/D3): the original Arm B strip keyed on ann_date only, but price gaps sit
-- at the ex-date (measured at ex_date-2/-1 relative to the book-closure start
-- date stored by the DPS payout scraper). psx_corporate_actions had no
-- ex_date at all, so the strip removed 0 events while 21 B75 + 15 B95 events
-- on real ex-dates survived (FFC -9.74%, CHCC -10.00%). These columns let the
-- corrected Arm B' strip on the true gap band (ex_date +/- 2 sessions) and
-- let the corrected Arm A' build total-return labels (per_share / pct from
-- the audited notice title, placed at the attributed ex_date).
--
-- ex_date semantics: the BOOK-CLOSURE START date (first date of the
-- "Book Closure from X to Y" range), identical to psx_dividends.ex_date so
-- the measured gap band (stored_ex_date -2/-1 sessions) is consistent across
-- both sources. NULL when the notice carries no parseable date (audited-only:
-- never guessed).
--
-- per_share: cash dividend per-share amount (Rs.), when the audited title
-- carries it ("Credit of Final Cash Dividend @ Rs. 6.00"). NULL otherwise.
-- pct: bonus/rights percentage ("@ 100%", "1:1"), when the audited title
-- carries it. NULL otherwise.

BEGIN;

ALTER TABLE public.psx_corporate_actions
    ADD COLUMN IF NOT EXISTS ex_date   DATE,
    ADD COLUMN IF NOT EXISTS per_share NUMERIC(16,4),
    ADD COLUMN IF NOT EXISTS pct       NUMERIC(10,4);

CREATE INDEX IF NOT EXISTS idx_corp_actions_sym_exdate
    ON public.psx_corporate_actions(symbol, ex_date DESC)
    WHERE ex_date IS NOT NULL;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260805140000_pilot_ex_dates.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
