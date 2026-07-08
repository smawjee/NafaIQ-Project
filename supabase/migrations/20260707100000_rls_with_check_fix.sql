-- ================================================================
-- RLS WITH CHECK Hardening
-- Adds WITH CHECK clauses to 4 user-data RLS policies that previously
-- had USING but no WITH CHECK. Without WITH CHECK, an authenticated user
-- could UPDATE a row to set user_id = someone else (because USING only
-- checks the existing row, not the new values).
--
-- Affected tables:
--   psx_watchlist  (v1, currently used by frontend)
--   psx_alerts     (v1, currently used by frontend)
--   psx_portfolios (v2)
--   psx_holdings   (v2, via parent portfolio join)
--
-- v2 tables (user_watchlist, price_alerts) already have WITH CHECK.
--
-- Run: Supabase Dashboard SQL Editor (no manual rollback — see below).
-- ================================================================

-- 1. psx_watchlist ----------------------------------------------------
DROP POLICY IF EXISTS "Users own their watchlist" ON public.psx_watchlist;
CREATE POLICY "Users own their watchlist"
    ON public.psx_watchlist
    FOR ALL
    TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 2. psx_alerts -------------------------------------------------------
DROP POLICY IF EXISTS "Users own their alerts" ON public.psx_alerts;
CREATE POLICY "Users own their alerts"
    ON public.psx_alerts
    FOR ALL
    TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 3. psx_portfolios ---------------------------------------------------
DROP POLICY IF EXISTS "Users own their portfolios" ON public.psx_portfolios;
CREATE POLICY "Users own their portfolios"
    ON public.psx_portfolios
    FOR ALL
    TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 4. psx_holdings (via parent portfolio join) -------------------------
DROP POLICY IF EXISTS "Users own their holdings through portfolio"
    ON public.psx_holdings;
CREATE POLICY "Users own their holdings through portfolio"
    ON public.psx_holdings
    FOR ALL
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.psx_portfolios
            WHERE public.psx_portfolios.id = public.psx_holdings.portfolio_id
              AND public.psx_portfolios.user_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.psx_portfolios
            WHERE public.psx_portfolios.id = public.psx_holdings.portfolio_id
              AND public.psx_portfolios.user_id = auth.uid()
        )
    );

-- ================================================================
-- VERIFICATION (run manually in Supabase SQL editor after this
-- migration applies successfully)
-- ================================================================
--
-- Replace <user-A-uuid> and <user-B-uuid> with two real auth.users IDs.
--
-- Test 1: User A cannot insert a row claiming User B owns it
--   SET LOCAL request.jwt.claim.sub = '<user-A-uuid>';
--   INSERT INTO public.psx_watchlist (user_id, symbol)
--     VALUES ('<user-B-uuid>', 'OGDC');
--   -- EXPECTED: ERROR — new row violates row-level security policy
--
-- Test 2: User A can insert their own row
--   SET LOCAL request.jwt.claim.sub = '<user-A-uuid>';
--   INSERT INTO public.psx_watchlist (user_id, symbol)
--     VALUES ('<user-A-uuid>', 'OGDC');
--   -- EXPECTED: 1 row inserted
--
-- Test 3: User A cannot update a row to change ownership
--   SET LOCAL request.jwt.claim.sub = '<user-A-uuid>';
--   UPDATE public.psx_watchlist
--     SET user_id = '<user-B-uuid>'
--     WHERE user_id = '<user-A-uuid>' AND symbol = 'OGDC';
--   -- EXPECTED: 0 rows updated
--
-- Test 4: psx_holdings cross-portfolio INSERT is blocked
--   -- As user A, attempt to insert a holding into user B's portfolio
--   SET LOCAL request.jwt.claim.sub = '<user-A-uuid>';
--   INSERT INTO public.psx_holdings (portfolio_id, symbol, shares)
--     VALUES (
--       (SELECT id FROM public.psx_portfolios WHERE user_id = '<user-B-uuid>' LIMIT 1),
--       'OGDC', 100
--     );
--   -- EXPECTED: ERROR
--
-- Reset the session role at the end:
--   RESET request.jwt.claim.sub;
-- ================================================================
