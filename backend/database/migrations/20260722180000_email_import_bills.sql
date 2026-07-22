-- Email-imported bills: source metadata and idempotency.
--
-- Transactions already dedupe on user_transactions.email_message_id. Bills need
-- the same protection now that Gmail invoice/subscription emails can create
-- user_bills rows.

BEGIN;

ALTER TABLE public.user_bills
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS note TEXT,
    ADD COLUMN IF NOT EXISTS email_message_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_bills_email_message
    ON public.user_bills(user_id, email_message_id)
    WHERE email_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_bills_email_source
    ON public.user_bills(user_id, source)
    WHERE source <> 'manual';

INSERT INTO public._applied_migrations (filename, applied_at)
VALUES ('20260722180000_email_import_bills.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;