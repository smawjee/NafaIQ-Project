-- Signals V4 no longer duplicates OHLCV storage.
-- The raw+verified copy design was dropped: there is no disk headroom for a
-- second full copy of psx_ohlcv, so V4 now reads psx_ohlcv directly with the
-- same serving-time corporate-action adjustment the legacy engine uses.
-- These two tables were never populated with authoritative history; dropping
-- them reclaims the space the nightly dual-write had begun to consume.

BEGIN;

DROP TABLE IF EXISTS public.psx_ohlcv_verified;
DROP TABLE IF EXISTS public.psx_ohlcv_raw;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260724100000_signals_v4_drop_duplicate_ohlcv.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
