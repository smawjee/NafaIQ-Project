-- Broker confirmation email import (Gmail attachments).
-- Backend-only tables: RLS is enabled with no authenticated policies.

CREATE TABLE IF NOT EXISTS public.broker_email_accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    broker_code TEXT NOT NULL,
    account_fingerprint TEXT NOT NULL,
    account_mask TEXT NOT NULL,
    mapped_portfolio_id BIGINT REFERENCES public.psx_portfolios(id) ON DELETE SET NULL,
    mode TEXT NOT NULL DEFAULT 'review' CHECK (mode IN ('review', 'auto')),
    verified_at TIMESTAMPTZ,
    adapter_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, broker_code, account_fingerprint)
);

CREATE TABLE IF NOT EXISTS public.broker_email_imports (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    gmail_message_id TEXT NOT NULL,
    gmail_thread_id TEXT,
    gmail_attachment_id TEXT NOT NULL,
    attachment_filename TEXT NOT NULL,
    attachment_sha256 TEXT NOT NULL,
    broker_code TEXT NOT NULL,
    account_id BIGINT REFERENCES public.broker_email_accounts(id) ON DELETE SET NULL,
    account_fingerprint TEXT,
    adapter_version TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('pending_review', 'unsupported', 'validation_failed', 'approved', 'imported', 'rejected')
    ),
    sender TEXT NOT NULL,
    sanitized_subject TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    trade_date DATE,
    settlement_date DATE,
    total_quantity INT,
    total_fees NUMERIC(14,2),
    total_net_amount NUMERIC(14,2),
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, gmail_message_id, gmail_attachment_id)
);

CREATE TABLE IF NOT EXISTS public.broker_email_import_items (
    id BIGSERIAL PRIMARY KEY,
    import_id BIGINT NOT NULL REFERENCES public.broker_email_imports(id) ON DELETE CASCADE,
    row_index INT NOT NULL,
    external_idempotency_key TEXT NOT NULL UNIQUE,
    contract_number TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity INT NOT NULL CHECK (quantity > 0),
    price NUMERIC(14,4) NOT NULL CHECK (price >= 0),
    fees NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (fees >= 0),
    net_amount NUMERIC(14,2) NOT NULL,
    settlement_date DATE,
    validation_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    stock_transaction_id BIGINT REFERENCES public.stock_transactions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, row_index)
);

CREATE INDEX IF NOT EXISTS idx_broker_email_imports_user_status
    ON public.broker_email_imports(user_id, status, id DESC);

CREATE INDEX IF NOT EXISTS idx_broker_email_accounts_user
    ON public.broker_email_accounts(user_id, broker_code);

ALTER TABLE public.stock_transactions
    ADD COLUMN IF NOT EXISTS broker_import_item_id BIGINT
    REFERENCES public.broker_email_import_items(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_transactions_broker_import_item
    ON public.stock_transactions(broker_import_item_id)
    WHERE broker_import_item_id IS NOT NULL;

ALTER TABLE public.broker_email_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_email_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_email_import_items ENABLE ROW LEVEL SECURITY;

GRANT ALL ON public.broker_email_accounts TO service_role;
GRANT ALL ON public.broker_email_imports TO service_role;
GRANT ALL ON public.broker_email_import_items TO service_role;
