-- Backup of drifted finance tables before consolidation onto user_* (2026-07-09)
-- Restore by running this file. Generated from live Supabase.

CREATE TABLE IF NOT EXISTS public."finance_transactions" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL,
  "merchant" text,
  "amount" numeric NOT NULL,
  "currency" text DEFAULT 'PKR'::text,
  "transaction_type" text,
  "category" text,
  "transaction_date" timestamptz,
  "source" text DEFAULT 'gmail'::text,
  "email_subject" text,
  "raw_text" text,
  "created_at" timestamptz DEFAULT now(),
  PRIMARY KEY ("id")
);
-- 2 row(s)
INSERT INTO public."finance_transactions" ("id", "user_id", "merchant", "amount", "currency", "transaction_type", "category", "transaction_date", "source", "email_subject", "raw_text", "created_at") VALUES ('720ed565-9d25-4200-ab7f-62ccd34806da', '08f43fcf-6789-4925-aefa-4614e33d48db', 'Xanders', '-2500', 'PKR', 'Expense', 'Food & Dining', '2026-07-08 09:44:51.934000+00:00', 'HBL Current', NULL, NULL, '2026-07-08 09:44:37.104727+00:00');
INSERT INTO public."finance_transactions" ("id", "user_id", "merchant", "amount", "currency", "transaction_type", "category", "transaction_date", "source", "email_subject", "raw_text", "created_at") VALUES ('c587bfe1-ec18-45fc-bafa-a645b88d963f', '92a9a491-650d-4455-81b0-8e3a0ce1ff3b', 'foodpanda', '-5000', 'PKR', 'Expense', 'Food & Dining', '2026-07-08 19:07:24.498000+00:00', 'HBL Current', NULL, NULL, '2026-07-08 19:07:25.061565+00:00');

CREATE TABLE IF NOT EXISTS public."finance_bills" (
  "id" uuid DEFAULT extensions.gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL,
  "name" text NOT NULL,
  "amount" numeric NOT NULL,
  "currency" text DEFAULT 'PKR'::text NOT NULL,
  "due_date" date,
  "due_label" text,
  "status" text DEFAULT 'UPCOMING'::text NOT NULL,
  "paid_at" timestamptz,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);
-- 2 row(s)
INSERT INTO public."finance_bills" ("id", "user_id", "name", "amount", "currency", "due_date", "due_label", "status", "paid_at", "created_at", "updated_at") VALUES ('07a9db92-877b-4486-9400-ee0cf11bc173', '08f43fcf-6789-4925-aefa-4614e33d48db', 'KSE', '2E+4', 'PKR', '2026-07-11', 'Jul 11', 'PAID', '2026-07-08 09:49:27.234000+00:00', '2026-07-08 09:45:26.115138+00:00', '2026-07-08 09:49:12.547810+00:00');
INSERT INTO public."finance_bills" ("id", "user_id", "name", "amount", "currency", "due_date", "due_label", "status", "paid_at", "created_at", "updated_at") VALUES ('e07d0bf8-15c2-4738-94c2-30eebeeaf438', '08f43fcf-6789-4925-aefa-4614e33d48db', 'KSE', '1E+4', 'PKR', '2026-07-07', 'Jul 7', 'UPCOMING', NULL, '2026-07-08 13:21:42.522603+00:00', '2026-07-08 13:21:42.522603+00:00');

CREATE TABLE IF NOT EXISTS public."budgets" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL,
  "category" text NOT NULL,
  "limit_amount" numeric DEFAULT 0 NOT NULL,
  "spent" numeric DEFAULT 0 NOT NULL,
  "tip" text,
  "created_at" timestamptz DEFAULT now(),
  "updated_at" timestamptz DEFAULT now(),
  PRIMARY KEY ("id")
);
-- 0 row(s)

CREATE TABLE IF NOT EXISTS public."goals" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL,
  "name" text NOT NULL,
  "target" numeric NOT NULL,
  "saved" numeric DEFAULT 0 NOT NULL,
  "emoji" text,
  "color" text,
  "ai" text,
  "target_date" date,
  "created_at" timestamptz DEFAULT now(),
  "updated_at" timestamptz DEFAULT now(),
  PRIMARY KEY ("id")
);
-- 2 row(s)
INSERT INTO public."goals" ("id", "user_id", "name", "target", "saved", "emoji", "color", "ai", "target_date", "created_at", "updated_at") VALUES ('bc344b56-2d2d-4e98-845b-2d39c5ce2c73', '7bdc124e-2b4b-461f-9b1b-d9262b43ee75', 'shopping', '15000', '0', '🎯', 'bull', 'New goal created. Start contributing to track your progress.', '2026-07-30', '2026-07-09 03:52:50.324170+00:00', '2026-07-09 03:52:50.324170+00:00');
INSERT INTO public."goals" ("id", "user_id", "name", "target", "saved", "emoji", "color", "ai", "target_date", "created_at", "updated_at") VALUES ('2ec299e1-d1ae-4676-b794-7ebb0ac1428f', '7bdc124e-2b4b-461f-9b1b-d9262b43ee75', 'food', '500', '500', '🎯', 'bull', 'New goal created. Start contributing to track your progress.', NULL, '2026-07-09 04:01:25.414202+00:00', '2026-07-09 09:09:05.752469+00:00');

CREATE TABLE IF NOT EXISTS public."email_import_items" (
  "id" uuid DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL,
  "provider" text DEFAULT 'gmail'::text NOT NULL,
  "provider_message_id" text NOT NULL,
  "subject" text,
  "snippet" text,
  "parsed_payload" jsonb DEFAULT '{}'::jsonb NOT NULL,
  "confidence" numeric DEFAULT 0 NOT NULL,
  "status" text NOT NULL,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);
-- 0 row(s)
