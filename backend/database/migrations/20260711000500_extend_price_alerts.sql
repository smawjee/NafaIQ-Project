-- ============================================================================
-- Extend price_alerts with channels and idempotency
-- Adds one_time, last_triggered_at, notify_push, notify_email, notes
-- to existing price_alerts without breaking changes.
-- ============================================================================

ALTER TABLE public.price_alerts
    ADD COLUMN IF NOT EXISTS one_time          BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS last_triggered_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS notify_push       BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS notify_email      BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS notes             TEXT;

CREATE INDEX IF NOT EXISTS idx_price_alerts_user_enabled
    ON public.price_alerts(user_id) WHERE enabled = TRUE;
