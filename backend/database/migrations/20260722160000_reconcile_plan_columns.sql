-- Reconcile the duplicated plan/tier columns (audit 2026-07-22 §3.3).
--
-- The subscription plan is duplicated:
--   profiles.plan        <- authoritative; the permission layer gates on this
--   profiles.tier        <- GENERATED ALWAYS AS (plan): a computed mirror that
--                           Postgres keeps in lockstep. NOT a bug (the audit
--                           misread it) and cannot be written directly, so it is
--                           left entirely alone here.
--   user_settings.plan   <- a stale copy: set to 'Free' once at insert, never
--                           updated, so it drifted. Two users read Premium in
--                           profiles but Free here.
--
-- The read path is already fixed in code: repositories/finance/settings.py now
-- sources `plan` from profiles via a join, so the display can no longer diverge.
-- This migration brings the STORED copies into line so the dead columns are not
-- a future landmine for anyone who queries them directly.
--
-- Non-destructive: only the two stale copies are updated to match the
-- authoritative profiles.plan. No column is dropped (the frontend's generated
-- types still reference them); profiles.plan itself is never written.
--
-- Touches only profiles.tier and user_settings.plan. No market data involved.

BEGIN;

-- 1. user_settings.plan -> match the user's authoritative profiles.plan.
DO $$
DECLARE
    n int;
BEGIN
    WITH synced AS (
        UPDATE public.user_settings s
        SET plan = p.plan, updated_at = now()
        FROM public.profiles p
        WHERE p.id = s.user_id
          AND s.plan IS DISTINCT FROM p.plan
        RETURNING 1
    )
    SELECT count(*) INTO n FROM synced;
    RAISE NOTICE 'user_settings.plan reconciled on % row(s).', n;
END $$;

-- 2. Verify user_settings.plan now agrees with the authoritative profiles.plan
--    for every user that has a settings row. (profiles.tier is generated, so it
--    is consistent by construction and not checked here.)
DO $$
DECLARE
    mismatches int;
BEGIN
    SELECT count(*) INTO mismatches
    FROM public.profiles p
    JOIN public.user_settings s ON s.user_id = p.id
    WHERE s.plan IS DISTINCT FROM p.plan;
    IF mismatches > 0 THEN
        RAISE EXCEPTION 'Plan reconciliation left % mismatch(es).', mismatches;
    END IF;
    RAISE NOTICE 'Verified: user_settings.plan matches profiles.plan.';
END $$;

INSERT INTO public._applied_migrations (filename, applied_at)
VALUES ('20260722160000_reconcile_plan_columns.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
