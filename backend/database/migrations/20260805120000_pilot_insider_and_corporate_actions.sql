-- Pilot data tables (2026-08-05 three-arm signals pilot).
--
-- ADDITIVE ONLY. Creates two NEW tables; nothing existing gains or alters
-- rows, no existing table is touched, and no existing scraper/scheduler reads
-- these. Purpose per the pre-registration in
-- backend/scripts/signals/RESEARCH_LOG.md (2026-08-05):
--
--   1. psx_insider_transactions — director/CEO/executive/substantial-
--      shareholder disclosures (PSX Reg. 5.6.1(d) / 5.6.4) parsed from the
--      DPS announcement feed ("Disclosure of Interest ..." Form-29 PDFs),
--      used by pilot Arm C (insider purchase event study). Insert-only;
--      source_row_hash makes every upsert idempotent.
--
--   2. psx_corporate_actions — bonus/rights/dividend notices attributed from
--      the psx_announcements archive (>=2023-12 per user decision; 2016-2022
--      stays quarantined as before), used by pilot Arm B to strip ex-cash /
--      ex-bonus dates from the limit-day event set. Insert-only.
--
-- Security: RLS deny-all for anon/authenticated (service_role only), the
-- same posture as the admin tables — browsers via PostgREST are denied;
-- the backend reaches these via SQLAlchemy/service_role.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Insider / director transactions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.psx_insider_transactions (
    -- DPS document id of the disclosure notice (280767 for .../280767.pdf).
    notice_id       TEXT NOT NULL,
    -- Row ordinal within the notice (one Form-29 can carry several trades).
    row_no          INT  NOT NULL,
    symbol          TEXT NOT NULL,
    company_name    TEXT,
    notice_date     DATE,
    txn_date        DATE,
    direction       TEXT NOT NULL,        -- buy | sell | gift | transfer | off_market | repo ...
    shares          NUMERIC(20,2),
    price           NUMERIC(16,4),
    description     TEXT,                 -- name of the person + position
    market          TEXT,                 -- Ready / Off Market / ...
    share_type      TEXT,                 -- CDC / Physical / ...
    title           TEXT NOT NULL DEFAULT '',
    pdf_url         TEXT,
    source          TEXT NOT NULL DEFAULT 'dps',
    -- sha256 of the parsed row; UNIQUE makes re-crawls idempotent.
    source_row_hash TEXT NOT NULL UNIQUE,
    parsed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (notice_id, row_no)
);

CREATE INDEX IF NOT EXISTS idx_insider_sym_date
    ON public.psx_insider_transactions(symbol, txn_date DESC);
CREATE INDEX IF NOT EXISTS idx_insider_txn_date
    ON public.psx_insider_transactions(txn_date DESC);
CREATE INDEX IF NOT EXISTS idx_insider_direction
    ON public.psx_insider_transactions(direction);

-- ---------------------------------------------------------------------------
-- 2. Corporate actions (attributed, audited-only)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.psx_corporate_actions (
    symbol          TEXT NOT NULL,
    ann_date        DATE NOT NULL,
    action_type     TEXT NOT NULL,        -- bonus | rights | dividend
    details         TEXT,                 -- title from psx_announcements
    source_row_hash TEXT NOT NULL UNIQUE,
    inserted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, ann_date, action_type, source_row_hash)
);

CREATE INDEX IF NOT EXISTS idx_corp_actions_sym
    ON public.psx_corporate_actions(symbol, ann_date DESC);
CREATE INDEX IF NOT EXISTS idx_corp_actions_date
    ON public.psx_corporate_actions(ann_date DESC);

-- ---------------------------------------------------------------------------
-- 3. RLS: deny-all for browsers, service_role only (admin-table posture)
-- ---------------------------------------------------------------------------
ALTER TABLE public.psx_insider_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.psx_corporate_actions   ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "insider_transactions_service_all" ON public.psx_insider_transactions;
CREATE POLICY "insider_transactions_service_all"
    ON public.psx_insider_transactions FOR ALL TO service_role
    USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "corporate_actions_service_all" ON public.psx_corporate_actions;
CREATE POLICY "corporate_actions_service_all"
    ON public.psx_corporate_actions FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- No anon/authenticated grants: browsers via PostgREST are denied.
GRANT ALL ON public.psx_insider_transactions TO service_role;
GRANT ALL ON public.psx_corporate_actions   TO service_role;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260805120000_pilot_insider_and_corporate_actions.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
