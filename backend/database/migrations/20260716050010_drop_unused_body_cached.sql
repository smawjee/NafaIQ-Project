-- psx_announcements.body_cached has been defined since 20260706120000 but
-- no code reads or writes it. Dropping it removes a dead 8 KB+ TEXT column
-- from every announcement row.
BEGIN;

ALTER TABLE public.psx_announcements DROP COLUMN IF EXISTS body_cached;

COMMIT;
