-- Add the missing foreign key: filings.announcement_id -> psx_announcements.id
-- (audit 2026-07-22 §3.2).
--
-- `filings` is a 1:1 extension of `psx_announcements` — it holds the extracted
-- PDF text for an announcement — yet no constraint expressed that relationship.
-- All 62 rows already resolve (verified before writing), so the FK is added
-- validated. ON DELETE CASCADE: a filing has no meaning without its announcement.
--
-- WHY NOT symbol FKs to psx_profile?
-- The audit also suggested foreign-keying every `symbol` column to
-- psx_profile.symbol. That was investigated and DELIBERATELY NOT DONE, because
-- it would reject legitimate data:
--   * psx_market_snapshot carries 47 live quotes for transient instrument
--     classes (*NC non-callable, *XD ex-dividend, *ETFXD, *WU, *XB) that trade
--     but are not in the DPS company catalogue. A symbol FK would make the next
--     market scrape DROP those 47 real quotes.
--   * user holdings/transactions carry 2 pre-existing hand-typed symbols (DSDS,
--     DF) that exist on no exchange. An FK could not even be added without first
--     deleting real users' rows.
-- The correct guard for user-entered symbols is the existing application check
-- (services/symbols.require_known_symbol), not a database constraint that fights
-- the market's own symbology.
--
-- Touches only the `filings` constraint set. No data is read, written or
-- deleted; no market prices are affected.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'filings_announcement_id_fkey'
          AND conrelid = 'public.filings'::regclass
    ) THEN
        ALTER TABLE public.filings
            ADD CONSTRAINT filings_announcement_id_fkey
            FOREIGN KEY (announcement_id)
            REFERENCES public.psx_announcements (id)
            ON DELETE CASCADE;
        RAISE NOTICE 'Added FK filings.announcement_id -> psx_announcements.id.';
    ELSE
        RAISE NOTICE 'FK filings_announcement_id_fkey already present.';
    END IF;
END $$;

INSERT INTO public._applied_migrations (filename, applied_at)
VALUES ('20260722150000_filings_announcement_fk.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
