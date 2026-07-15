-- Migration ledger: tracks which migrations have been applied so that CI
-- and the apply scripts can detect "migration X not applied" vs "test
-- written wrong" reliably. The current test (test_migrations_applied.py)
-- only checks end-state; this ledger enables per-migration assertion.
--
-- CAVEATS (read before trusting this table):
--   * The back-fill below records every migration file that existed when this
--     ledger was created. It is a best-effort reconstruction: `applied_at` is
--     set to now() at back-fill time, NOT the real historical apply time,
--     which is unknowable after the fact.
--   * `sha256` is left NULL for back-filled rows, so drift detection against
--     file contents is not yet possible for them.
--   * Nothing writes to this table automatically yet. Until the apply scripts
--     INSERT on each apply, rows for NEW migrations must be added by hand or
--     the ledger will silently go stale.
-- Re-runnable: guarded policy + ON CONFLICT DO NOTHING, all inside one
-- transaction so a failure cannot leave the ledger half-created.

BEGIN;

CREATE TABLE IF NOT EXISTS public._applied_migrations (
    filename   TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sha256     TEXT
);

ALTER TABLE public._applied_migrations ENABLE ROW LEVEL SECURITY;

-- Only service_role can write. No read policy needed (admin queries only).
-- DROP first: CREATE POLICY has no IF NOT EXISTS, so an unguarded re-run
-- fails with 42710 (policy already exists).
DROP POLICY IF EXISTS "_applied_migrations_admin" ON public._applied_migrations;
CREATE POLICY "_applied_migrations_admin" ON public._applied_migrations
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- service_role bypasses RLS, so the policy above is belt-and-braces for any
-- future non-superuser admin role. GRANT ALL already implies SELECT.
GRANT ALL ON public._applied_migrations TO service_role;

-- Back-fill: every migration file present in backend/database/migrations at
-- the time this ledger was written (41 files). Generated from disk
-- rather than hand-listed — the previous hand-written list recorded 37 rows,
-- omitted 5 real migrations, and included a phantom entry for
-- 20260716010000_apply_sector_map.sql, which exists only as `.sql.disabled`
-- and therefore never ran.
INSERT INTO public._applied_migrations (filename) VALUES
    ('20260618092009_0ee05a2f-9707-4ee4-9baf-d8e9aee10d8a.sql'),
    ('20260618092033_131963bb-5ab6-4d41-a79e-8aadb8d24506.sql'),
    ('20260706120000_psx_module.sql'),
    ('20260706130000_psx_realtime_and_fix.sql'),
    ('20260707100000_rls_with_check_fix.sql'),
    ('20260708011922_add_idx_psx_portfolios_user_id.sql'),
    ('20260709010000_user_alerts_and_notifications.sql'),
    ('20260710000000_user_finance.sql'),
    ('20260710010000_index_ohlcv.sql'),
    ('20260711000000_role_and_plans.sql'),
    ('20260711000100_stock_transactions.sql'),
    ('20260711000200_watchlist_v2.sql'),
    ('20260711000300_zakat.sql'),
    ('20260711000400_alert_events.sql'),
    ('20260711000500_extend_price_alerts.sql'),
    ('20260711000600_user_data_hardening_and_limits.sql'),
    ('20260712000000_consolidate_finance_onto_user_tables.sql'),
    ('20260712010000_add_logoid_to_psx_profile.sql'),
    ('20260712020000_link_user_transactions_to_stock_transactions.sql'),
    ('20260712030000_profiles_plan_selected_at.sql'),
    ('20260712110000_performance_indexes.sql'),
    ('20260712120000_ai_tutor_history_usage.sql'),
    ('20260714120000_ai_reports.sql'),
    ('20260714130000_db_integrity_cleanup.sql'),
    ('20260714140000_ai_reports_shared_unique_nulls.sql'),
    ('20260715000000_patch_market_snapshot.sql'),
    ('20260715010000_new_data_tables.sql'),
    ('20260715020000_ohlcv_adjustment_and_shariah.sql'),
    ('20260715030000_rls_grants_and_indexes.sql'),
    ('20260716000000_add_listed_in.sql'),
    ('20260716020000_mufap_performance_indexes.sql'),
    ('20260716030000_tighten_grants.sql'),
    ('20260716030010_tighten_grants_mufap.sql'),
    ('20260716040000_add_ttls.sql'),
    ('20260716040010_drop_duplicate_ttl_indexes.sql'),
    ('20260716050000_data_source_health.sql'),
    ('20260716050010_drop_unused_body_cached.sql'),
    ('20260716050020_create_migration_ledger.sql'),
    ('20260716050030_drop_v1_schema.sql'),
    ('20260716060000_cleanup_duplicates_and_orphans.sql'),
    ('20260716070000_analyze_and_refresh.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
