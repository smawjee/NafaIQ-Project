-- Link a personal-finance transaction to the stock trade that created it
-- (2026-07-09). When a holding is bought/sold we record an Investment
-- transaction in user_transactions; this FK ties it to the originating
-- stock_transactions row. ON DELETE SET NULL keeps the finance record (the
-- cash movement really happened) but drops the dangling link if the trade
-- row is ever removed.
ALTER TABLE public.user_transactions
    ADD COLUMN IF NOT EXISTS stock_transaction_id BIGINT
    REFERENCES public.stock_transactions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_user_transactions_stock_txn
    ON public.user_transactions(stock_transaction_id)
    WHERE stock_transaction_id IS NOT NULL;
