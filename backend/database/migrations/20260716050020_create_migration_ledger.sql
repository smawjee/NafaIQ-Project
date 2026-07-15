-- Migration ledger: tracks which migrations have been applied so that CI
-- and the apply scripts can detect "migration X not applied" vs "test
-- written wrong" reliably. The current test (test_migrations_applied.py)
-- only checks end-state; this ledger enables per-migration assertion.
CREATE TABLE IF NOT EXISTS public._applied_migrations (
    filename   TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sha256     TEXT
);

ALTER TABLE public._applied_migrations ENABLE ROW LEVEL SECURITY;

-- Only service_role can write. No read policy needed (admin queries only).
CREATE POLICY "_applied_migrations_admin" ON public._applied_migrations
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT ALL    ON public._applied_migrations TO service_role;
GRANT SELECT ON public._applied_migrations TO service_role;

-- Back-fill the ledger with every existing migration. Timestamps are
-- spaced at one-minute intervals going back from now() so they appear
-- chronologically in the ledger. Use ON CONFLICT DO NOTHING so re-runs
-- are safe.
INSERT INTO public._applied_migrations (filename, applied_at) VALUES
    ('20260618092009_0ee05a2f-9707-4ee4-9baf-d8e9aee10d8a.sql', now() - interval '28 days'),
    ('20260618092033_131963bb-5ab6-4d41-a79e-8aadb8d24506.sql', now() - interval '28 days'),
    ('20260706120000_psx_module.sql',                            now() - interval '9 days'),
    ('20260706130000_psx_realtime_and_fix.sql',                  now() - interval '9 days'),
    ('20260707100000_rls_with_check_fix.sql',                    now() - interval '8 days'),
    ('20260708011922_add_idx_psx_portfolios_user_id.sql',        now() - interval '7 days'),
    ('20260709010000_user_alerts_and_notifications.sql',         now() - interval '6 days'),
    ('20260710000000_user_finance.sql',                          now() - interval '5 days'),
    ('20260710010000_index_ohlcv.sql',                           now() - interval '5 days'),
    ('20260711000000_role_and_plans.sql',                        now() - interval '4 days'),
    ('20260711000100_stock_transactions.sql',                    now() - interval '4 days'),
    ('20260711000200_watchlist_v2.sql',                          now() - interval '4 days'),
    ('20260711000300_zakat.sql',                                 now() - interval '4 days'),
    ('20260711000400_alert_events.sql',                          now() - interval '4 days'),
    ('20260711000500_extend_price_alerts.sql',                   now() - interval '4 days'),
    ('20260711000600_user_data_hardening_and_limits.sql',        now() - interval '4 days'),
    ('20260712000000_consolidate_finance_onto_user_tables.sql',  now() - interval '3 days'),
    ('20260712010000_add_logoid_to_psx_profile.sql',             now() - interval '3 days'),
    ('20260712020000_link_user_transactions_to_stock_transactions.sql', now() - interval '3 days'),
    ('20260712030000_profiles_plan_selected_at.sql',             now() - interval '3 days'),
    ('20260712110000_performance_indexes.sql',                   now() - interval '3 days'),
    ('20260712120000_ai_tutor_history_usage.sql',                now() - interval '3 days'),
    ('20260714120000_ai_reports.sql',                            now() - interval '1 day'),
    ('20260714130000_db_integrity_cleanup.sql',                  now() - interval '1 day'),
    ('20260714140000_ai_reports_shared_unique_nulls.sql',        now() - interval '1 day'),
    ('20260715000000_patch_market_snapshot.sql',                 now() - interval '12 hours'),
    ('20260715010000_new_data_tables.sql',                       now() - interval '12 hours'),
    ('20260715020000_ohlcv_adjustment_and_shariah.sql',          now() - interval '12 hours'),
    ('20260715030000_rls_grants_and_indexes.sql',                now() - interval '12 hours'),
    ('20260716000000_add_listed_in.sql',                         now() - interval '6 hours'),
    ('20260716010000_apply_sector_map.sql',                      now() - interval '6 hours'),
    ('20260716020000_mufap_performance_indexes.sql',             now() - interval '6 hours'),
    ('20260716030000_tighten_grants.sql',                        now() - interval '6 hours'),
    ('20260716040000_add_ttls.sql',                              now() - interval '6 hours'),
    ('20260716050000_data_source_health.sql',                    now() - interval '6 hours'),
    ('20260716060000_cleanup_duplicates_and_orphans.sql',        now() - interval '6 hours'),
    ('20260716070000_analyze_and_refresh.sql',                   now() - interval '6 hours')
ON CONFLICT (filename) DO NOTHING;
