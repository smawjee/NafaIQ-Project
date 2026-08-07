-- Opening balance for the running (carried-forward) finance balance.
--
-- WHY
-- `finance.summary()` computed `savings = income - expenses` strictly WITHIN a
-- single month, so every month started from zero: money left unspent in July
-- never appeared in August. The app therefore only ever described the current
-- month, and a user could not see what they actually had available.
--
-- A running balance needs a starting point that is not derivable from the
-- transaction table — the table only records flows, not the balance the user
-- already held when they started using the app. These two columns are that
-- anchor: `opening_balance` is what the user had on `opening_balance_date`, and
-- every month from that date forward contributes (income - expenses) on top.
--
-- Both are nullable/zero-defaulted, so a user who never sets one keeps the
-- previous behaviour with an opening balance of 0 and simply accumulates their
-- recorded net from the earliest month on file.

BEGIN;

ALTER TABLE public.user_settings
    ADD COLUMN IF NOT EXISTS opening_balance      NUMERIC(14, 2) NOT NULL DEFAULT 0,
    -- The month this balance was true as of. Months strictly BEFORE it are
    -- excluded from the running total: they predate the user's own starting
    -- figure, and counting them would double-count money already inside it.
    ADD COLUMN IF NOT EXISTS opening_balance_date DATE;

COMMENT ON COLUMN public.user_settings.opening_balance IS 'Balance the user held on opening_balance_date; anchors the running carried-forward balance';
COMMENT ON COLUMN public.user_settings.opening_balance_date IS 'Date opening_balance was accurate as of; months before it are excluded from the running total';

COMMIT;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260806170000_finance_opening_balance.sql', now())
ON CONFLICT (filename) DO NOTHING;
