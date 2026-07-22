-- Backfill legacy email-imported transactions.
--
-- The importer used to store the literal "bank_email" in the free-text
-- user_transactions.source column, which the finance UI renders verbatim as the
-- transaction's "way of transaction" — so users saw "bank_email" instead of the
-- bank. New imports now store the bank name derived from the sender
-- ("Meezan Bank · auto"). The exact bank can't be recovered for old rows (the
-- sender was never stored), so relabel them to a friendly generic.
--
-- Safe/idempotent: only touches rows whose source is exactly 'bank_email'.

UPDATE user_transactions
SET source = 'Bank email'
WHERE source = 'bank_email';
