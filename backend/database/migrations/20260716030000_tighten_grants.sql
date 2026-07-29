-- Tighten GRANT ALL → GRANT SELECT for the 8 new Workstream D tables.
-- RLS already blocks writes but the grants should be correct for defense in depth.
-- Spec: (internal workstream plan)

DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'macro_rates', 'psx_news', 'filings',
        'psx_unusual_activity',
        'psx_financials_annual', 'psx_financials_quarterly'
    ]) LOOP
        EXECUTE format('REVOKE ALL ON TABLE %I FROM anon, authenticated', tbl);
        EXECUTE format('GRANT SELECT ON TABLE %I TO anon, authenticated', tbl);
    END LOOP;
END $$;
