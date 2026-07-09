-- ============================================================================
-- Role and Plan Features
-- Adds plan_features table for tier-based feature gating.
-- Tier names match the landing page pricing section: Free, Pro, Premium.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.plan_features (
    plan                       TEXT PRIMARY KEY
                               CHECK (plan IN ('Free', 'Pro', 'Premium')),
    rank                       INT  NOT NULL UNIQUE,
    max_watchlist              INT  NOT NULL,
    max_price_alerts           INT  NOT NULL,
    max_portfolios              INT  NOT NULL,
    max_holdings_per_portfolio INT  NOT NULL,
    max_budgets                INT  NOT NULL,
    max_bills                  INT  NOT NULL,
    max_goals                  INT  NOT NULL,
    max_finance_history_days   INT  NOT NULL,
    ai_tutor_daily_limit       INT,
    ai_reports_per_period      INT,
    ai_reports_period          TEXT
                               CHECK (ai_reports_period IN ('day', 'week', 'month') OR ai_reports_period IS NULL),
    has_email_alerts           BOOLEAN NOT NULL DEFAULT FALSE,
    has_push_alerts            BOOLEAN NOT NULL DEFAULT FALSE,
    has_export                 BOOLEAN NOT NULL DEFAULT FALSE,
    has_multi_currency         BOOLEAN NOT NULL DEFAULT FALSE,
    has_realtime_psx           BOOLEAN NOT NULL DEFAULT FALSE,
    has_screener_full          BOOLEAN NOT NULL DEFAULT FALSE,
    has_webhook_integration    BOOLEAN NOT NULL DEFAULT FALSE,
    has_api_access             BOOLEAN NOT NULL DEFAULT FALSE,
    description                TEXT,
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO public.plan_features
    (plan, rank, max_watchlist, max_price_alerts, max_portfolios, max_holdings_per_portfolio,
     max_budgets, max_bills, max_goals, max_finance_history_days,
     ai_tutor_daily_limit, ai_reports_per_period, ai_reports_period,
     has_email_alerts, has_push_alerts, has_export, has_multi_currency,
     has_realtime_psx, has_screener_full, has_webhook_integration, has_api_access, description)
VALUES
    ('Free',    0,    10,    5, 1,  20,   5,  5,  3,   30,  10, 3, 'month', FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, 'Free tier with delayed data'),
    ('Pro',     1,    50,   50, 5, 100,  20, 30, 10,  365, NULL, 1, 'week',  TRUE,  TRUE,  TRUE,  TRUE,  TRUE,  TRUE,  FALSE, FALSE, 'Pro tier with real-time data'),
    ('Premium', 2, 10000, 10000, 1000, 10000, 10000, 10000, 10000, 36500, NULL, NULL, NULL, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, 'Premium tier with all features')
ON CONFLICT (plan) DO UPDATE SET
    rank = EXCLUDED.rank,
    max_watchlist = EXCLUDED.max_watchlist,
    max_price_alerts = EXCLUDED.max_price_alerts,
    max_portfolios = EXCLUDED.max_portfolios,
    max_holdings_per_portfolio = EXCLUDED.max_holdings_per_portfolio,
    max_budgets = EXCLUDED.max_budgets,
    max_bills = EXCLUDED.max_bills,
    max_goals = EXCLUDED.max_goals,
    max_finance_history_days = EXCLUDED.max_finance_history_days,
    ai_tutor_daily_limit = EXCLUDED.ai_tutor_daily_limit,
    ai_reports_per_period = EXCLUDED.ai_reports_per_period,
    ai_reports_period = EXCLUDED.ai_reports_period,
    has_email_alerts = EXCLUDED.has_email_alerts,
    has_push_alerts = EXCLUDED.has_push_alerts,
    has_export = EXCLUDED.has_export,
    has_multi_currency = EXCLUDED.has_multi_currency,
    has_realtime_psx = EXCLUDED.has_realtime_psx,
    has_screener_full = EXCLUDED.has_screener_full,
    has_webhook_integration = EXCLUDED.has_webhook_integration,
    has_api_access = EXCLUDED.has_api_access,
    description = EXCLUDED.description,
    updated_at = now();

ALTER TABLE public.plan_features ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read plan features"
    ON public.plan_features
    FOR SELECT
    USING (true);

GRANT SELECT ON public.plan_features TO anon, authenticated;
GRANT ALL ON public.plan_features TO service_role;

-- profiles.tier is an alias of profiles.plan, kept for naming consistency.
-- We do not duplicate storage; only enforce a check constraint.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'tier'
    ) THEN
        ALTER TABLE public.profiles ADD COLUMN tier TEXT
            GENERATED ALWAYS AS (plan) STORED
            CHECK (tier IS NULL OR tier IN ('Free', 'Pro', 'Premium'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_profiles_plan ON public.profiles(plan);
