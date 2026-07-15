-- Tighten grants for the two Workstream D tables that were skipped in
-- 20260716030000. The current end state (anon SELECT, service_role ALL)
-- is correct, but the explicit REVOKE + GRANT defends against a future
-- migration that adds columns and silently grants implicit access.
BEGIN;

REVOKE ALL ON public.psx_mutual_funds     FROM anon, authenticated;
REVOKE ALL ON public.psx_fund_nav_history FROM anon, authenticated;

GRANT SELECT ON public.psx_mutual_funds     TO anon, authenticated;
GRANT SELECT ON public.psx_fund_nav_history TO anon, authenticated;

GRANT ALL ON public.psx_mutual_funds     TO service_role;
GRANT ALL ON public.psx_fund_nav_history TO service_role;

COMMIT;
