-- ================================================================
-- Email activity notifications
-- Adds a second email-preference bucket (email_activity) so routine
-- receipt/activity emails don't ride the same toggle as threshold
-- alerts (email_alerts), and widens in_app_notifications.kind for the
-- new activity notification categories.
-- Run: via Supabase Dashboard SQL Editor or supabase db push
-- ================================================================

-- 1. New opt-in preference for activity/receipt emails (default off so
--    existing users aren't retroactively emailed on every action).
ALTER TABLE public.user_notification_prefs
    ADD COLUMN IF NOT EXISTS email_activity BOOLEAN NOT NULL DEFAULT false;

-- 2. Widen the in_app_notifications.kind CHECK for activity categories.
ALTER TABLE public.in_app_notifications
    DROP CONSTRAINT IF EXISTS in_app_notifications_kind_check;
ALTER TABLE public.in_app_notifications
    ADD CONSTRAINT in_app_notifications_kind_check
    CHECK (kind IN (
        'price_alert', 'bill', 'budget', 'goal', 'system',
        'transaction', 'trade', 'account', 'watchlist', 'goal_complete'
    ));
