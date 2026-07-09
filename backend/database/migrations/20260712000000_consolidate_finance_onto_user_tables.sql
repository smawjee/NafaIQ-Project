-- Consolidate finance data onto the canonical user_* tables (2026-07-09).
--
-- The active application (backend services/finance_routes.py and the web
-- finance.tsx via the use-finance-* hooks) reads and writes:
--   user_transactions, user_budgets, user_goals, user_bills
--
-- The five tables dropped below were created directly against the database
-- (outside the migration history -- schema drift) as scaffolding for a
-- direct-Supabase finance + email-import path that was never wired into the
-- app (lib/finance/financeTransactions.ts and financeBills.ts were imported
-- nowhere). They held only developer test rows.
--
-- A full DDL + data backup was taken before this migration:
--   database/backups/20260709_dropped_finance_tables_backup.sql
--
-- After this migration the live schema matches the migration history exactly
-- (29 tables). Email-import fields, when that feature is built, should be added
-- to user_transactions rather than reintroducing a parallel table.

DROP TABLE IF EXISTS public.finance_transactions;
DROP TABLE IF EXISTS public.finance_bills;
DROP TABLE IF EXISTS public.email_import_items;
DROP TABLE IF EXISTS public.budgets;
DROP TABLE IF EXISTS public.goals;
