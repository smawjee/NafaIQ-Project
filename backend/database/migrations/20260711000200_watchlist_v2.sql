-- ============================================================================
-- Watchlist v2 Additions
-- Adds future channel notification fields to user_watchlist.
-- Does not change the primary key, RLS, or existing behavior.
-- ============================================================================

ALTER TABLE public.user_watchlist
    ADD COLUMN IF NOT EXISTS notify_push  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS notify_email BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS notes        TEXT;

CREATE INDEX IF NOT EXISTS idx_user_watchlist_user
    ON public.user_watchlist(user_id);
