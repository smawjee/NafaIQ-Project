-- ================================================================
-- Bank-email transaction auto-import (Gmail API / OAuth)
--
-- Stores a per-user Gmail connection that a scheduled job polls for bank
-- transaction-alert emails, and gives user_transactions an idempotency key so
-- re-polling the same message can never create a duplicate transaction.
--
-- Per the directive in 20260712000000_consolidate_finance_onto_user_tables.sql
-- ("Email-import fields, when that feature is built, should be added to
-- user_transactions rather than reintroducing a parallel table"), the parsed
-- result lands in user_transactions -- no parallel finance/import table.
--
-- Run: via Supabase Dashboard SQL Editor or supabase db push
-- ================================================================

-- 1. Per-user Gmail connection.
--
-- SECURITY: refresh_token_enc holds the Google OAuth refresh token encrypted at
-- rest (Fernet, key = EMAIL_CRED_ENC_KEY in the backend env). We never store a
-- mailbox password -- the grant is read-only (gmail.readonly) and the user can
-- revoke it at any time from their Google account.
--
-- RLS is enabled with NO policy for `authenticated`, so clients can never read
-- this table at all -- the token is only reachable by the backend's direct
-- Postgres connection (service role bypasses RLS), the same access model the
-- alert evaluators rely on. Status is served by GET /api/integrations/email.
CREATE TABLE IF NOT EXISTS public.user_email_integrations (
    user_id           UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    provider          TEXT NOT NULL DEFAULT 'gmail' CHECK (provider IN ('gmail')),
    -- The Google account actually connected, which may differ from the NafaIQ
    -- login email.
    google_email      TEXT NOT NULL,
    refresh_token_enc TEXT NOT NULL,
    scope             TEXT,
    enabled           BOOLEAN NOT NULL DEFAULT true,
    -- Gmail internalDate watermark (ms since epoch): only messages newer than
    -- this are fetched. 0 = first sync.
    last_internal_date BIGINT NOT NULL DEFAULT 0,
    last_polled_at    TIMESTAMPTZ,
    -- Set when the grant dies (Google Testing-mode refresh tokens expire after
    -- 7 days, or the user revoked access) so the UI can prompt a reconnect.
    last_error        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_email_integrations_enabled
    ON public.user_email_integrations(enabled) WHERE enabled = true;

ALTER TABLE public.user_email_integrations ENABLE ROW LEVEL SECURITY;
-- Intentionally NO policy and NO grant to `authenticated`: this table holds an
-- OAuth refresh token and is backend-only.

-- 2. Idempotency key for email-sourced transactions (the Gmail message id).
ALTER TABLE public.user_transactions
    ADD COLUMN IF NOT EXISTS email_message_id TEXT;

-- One transaction per (user, email message). Partial so manually added rows
-- (email_message_id IS NULL) are unaffected.
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_transactions_user_email_message
    ON public.user_transactions(user_id, email_message_id)
    WHERE email_message_id IS NOT NULL;
