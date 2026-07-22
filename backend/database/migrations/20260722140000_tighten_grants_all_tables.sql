-- Remove default write/TRUNCATE grants from anon + authenticated (audit §4).
--
-- THE PROBLEM
-- Supabase's default grants give anon and authenticated
-- INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES and TRIGGER on every table.
-- RLS blocks the row-level operations, so this is not an open door — with one
-- exception that matters:
--
--     TRUNCATE IS NOT SUBJECT TO ROW LEVEL SECURITY.
--
-- No policy can stop it. A role holding TRUNCATE can empty a table outright,
-- RLS or not. That applied to 40 of 48 tables, including user_transactions,
-- profiles, stock_transactions and psx_ohlcv.
--
-- 20260716030000_tighten_grants.sql started this work and covered 6 tables
-- (filings, macro_rates, psx_news, psx_unusual_activity, psx_financials_*).
-- This finishes the job for the rest.
--
-- WHAT THIS DOES NOT CHANGE
-- Reads are untouched. Every table that is publicly readable today stays
-- publicly readable: SELECT is re-granted immediately, and RLS policies are not
-- modified at all. The app's own writes go through the backend using the
-- service_role key, which bypasses both grants and RLS — so market data
-- collection, the schedulers and every API write path are unaffected.
--
-- Deliberate exception: psx_data_source_health keeps its per-COLUMN grants from
-- 20260716130000 (which withhold last_error_message from clients). A blanket
-- table-level GRANT SELECT here would silently widen that back out, so it is
-- excluded and handled explicitly.
--
-- Idempotent: REVOKE/GRANT are declarative.

BEGIN;

DO $$
DECLARE
    r            record;
    n_revoked    int := 0;
    -- Tables whose read access is column-scoped and must not be re-granted
    -- at table level.
    column_scoped text[] := ARRAY['psx_data_source_health'];
    -- Public reference data: readable by anyone (RLS still applies).
    public_read  text[] := ARRAY[
        'psx_ohlcv', 'psx_market_snapshot', 'psx_profile', 'psx_fundamentals',
        'psx_index_eod', 'psx_signals', 'psx_signals_v2', 'psx_announcements',
        'psx_dividends', 'psx_news', 'psx_ticks', 'psx_unusual_activity',
        'psx_mutual_funds', 'psx_fund_nav_history', 'psx_financials_annual',
        'psx_financials_quarterly', 'filings', 'macro_rates', 'plan_features'
    ];
BEGIN
    FOR r IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.relname
    LOOP
        -- Strip every default privilege from the two client roles.
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM anon, authenticated',
            r.relname
        );
        n_revoked := n_revoked + 1;

        IF r.relname = ANY(column_scoped) THEN
            CONTINUE;  -- per-column grants are restored below
        END IF;

        IF r.relname = ANY(public_read) THEN
            -- Public reference data: anonymous browsing must keep working.
            EXECUTE format(
                'GRANT SELECT ON TABLE public.%I TO anon, authenticated', r.relname
            );
        ELSE
            -- User-owned data: only a signed-in user may read, and RLS still
            -- restricts them to their own rows.
            EXECUTE format(
                'GRANT SELECT ON TABLE public.%I TO authenticated', r.relname
            );
        END IF;
    END LOOP;

    RAISE NOTICE 'Revoked default grants on % tables; SELECT re-granted.', n_revoked;
END $$;

-- Restore the column-scoped health grants exactly as 20260716130000 set them:
-- every column EXCEPT last_error_message, which can contain raw str(e) text.
GRANT SELECT (source, last_success, last_error, rows_updated, refreshed_at)
    ON public.psx_data_source_health TO anon, authenticated;

-- service_role must retain full access — it is what the backend writes with.
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;

-- Verify: no client role should hold a write privilege anywhere.
DO $$
DECLARE
    leftovers int;
BEGIN
    SELECT count(*) INTO leftovers
    FROM information_schema.role_table_grants
    WHERE table_schema = 'public'
      AND grantee IN ('anon', 'authenticated')
      AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER');

    IF leftovers > 0 THEN
        RAISE EXCEPTION
            '% write grant(s) still held by anon/authenticated — tighten failed.',
            leftovers;
    END IF;
    RAISE NOTICE 'Verified: anon/authenticated hold no write privileges.';
END $$;

INSERT INTO public._applied_migrations (filename, applied_at)
VALUES ('20260722140000_tighten_grants_all_tables.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
