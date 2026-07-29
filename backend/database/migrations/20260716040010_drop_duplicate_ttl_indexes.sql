-- 20260716040000_add_ttls.sql re-created two indexes that already existed
-- from 20260715010000, leaving one duplicate per table. This migration
-- drops the older copies (kept the newer ones, which are descriptive).
BEGIN;

DROP INDEX IF EXISTS public.idx_psx_news_pub;
DROP INDEX IF EXISTS public.idx_psx_unusual_ts;

COMMIT;
