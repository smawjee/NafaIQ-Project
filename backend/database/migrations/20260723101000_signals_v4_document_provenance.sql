-- Extend existing filing storage with provenance needed by V4 research.

BEGIN;

ALTER TABLE IF EXISTS public.filings
    ADD COLUMN IF NOT EXISTS document_hash TEXT;

ALTER TABLE IF EXISTS public.psx_signal_events
    ADD COLUMN IF NOT EXISTS revision INT NOT NULL DEFAULT 1;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260723101000_signals_v4_document_provenance.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
