"""Pytest: verify required migrations are applied to Supabase.

Checks each migration's expected schema changes against the live DB.

Requires a live database — it inspects the real schema, so there is nothing
meaningful to assert without one. Guarded like the other live-DB suites (see
tests/test_sell_holding.py) so a credential-free CI run skips it instead of
reporting a false failure.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest
from sqlalchemy import text

from app.config import settings
from app.db.sqlalchemy import ensure_reflected, get_engine

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)


@dataclass
class Check:
    name: str
    sql: str
    description: str = ""


@dataclass
class MigrationCheck:
    filename: str
    description: str
    checks: List[Check]


CHECKS: List[MigrationCheck] = [
    MigrationCheck(
        filename="20260618092009_0ee05a2f-9707-4ee4-9baf-d8e9aee10d8a.sql",
        description="Profiles + auth trigger",
        checks=[
            Check("profiles table exists", "SELECT to_regclass('public.profiles') IS NOT NULL"),
            Check("profiles.display_name column", "SELECT 1 FROM information_schema.columns WHERE table_name='profiles' AND column_name='display_name'"),
            Check("profiles.plan column", "SELECT 1 FROM information_schema.columns WHERE table_name='profiles' AND column_name='plan'"),
            Check("profiles.avatar_url column", "SELECT 1 FROM information_schema.columns WHERE table_name='profiles' AND column_name='avatar_url'"),
            Check("handle_new_user function exists", "SELECT 1 FROM pg_proc WHERE proname='handle_new_user'"),
            Check("update_updated_at_column function exists", "SELECT 1 FROM pg_proc WHERE proname='update_updated_at_column'"),
            Check("on_auth_user_created trigger exists", "SELECT 1 FROM pg_trigger WHERE tgname='on_auth_user_created'"),
            Check("RLS enabled on profiles", "SELECT relrowsecurity FROM pg_class WHERE relname='profiles'"),
        ],
    ),
    MigrationCheck(
        filename="20260618092033_131963bb-5ab6-4d41-a79e-8aadb8d24506.sql",
        description="Tighten security: REVOKE EXECUTE on functions",
        checks=[
            Check("handle_new_user EXECUTE revoked from PUBLIC",
                  "SELECT 1 FROM information_schema.routine_privileges "
                  "WHERE routine_name='handle_new_user' AND grantee='PUBLIC'"),
            Check("update_updated_at_column EXECUTE revoked from PUBLIC",
                  "SELECT 1 FROM information_schema.routine_privileges "
                  "WHERE routine_name='update_updated_at_column' AND grantee='PUBLIC'"),
        ],
    ),
    MigrationCheck(
        filename="20260706120000_psx_module.sql",
        description="PSX module: 12 tables + indexes + RLS",
        checks=[
            Check("psx_market_snapshot table", "SELECT to_regclass('public.psx_market_snapshot') IS NOT NULL"),
            Check("psx_ohlcv table", "SELECT to_regclass('public.psx_ohlcv') IS NOT NULL"),
            Check("psx_fundamentals table", "SELECT to_regclass('public.psx_fundamentals') IS NOT NULL"),
            Check("psx_profile table", "SELECT to_regclass('public.psx_profile') IS NOT NULL"),
            Check("psx_announcements table", "SELECT to_regclass('public.psx_announcements') IS NOT NULL"),
            Check("psx_dividends table", "SELECT to_regclass('public.psx_dividends') IS NOT NULL"),
            Check("psx_index_eod table", "SELECT to_regclass('public.psx_index_eod') IS NOT NULL"),
            Check("psx_ticks table", "SELECT to_regclass('public.psx_ticks') IS NOT NULL"),
            # psx_watchlist / psx_alerts (v1) were superseded by user_watchlist +
            # price_alerts and DROPPED by 20260716050030_drop_v1_schema.sql
            # (applied 2026-07-22). Both must now be absent.
            Check("psx_watchlist table (v1) dropped", "SELECT to_regclass('public.psx_watchlist') IS NULL"),
            Check("psx_alerts table (v1) dropped", "SELECT to_regclass('public.psx_alerts') IS NULL"),
            Check("psx_portfolios table", "SELECT to_regclass('public.psx_portfolios') IS NOT NULL"),
            Check("psx_holdings table", "SELECT to_regclass('public.psx_holdings') IS NOT NULL"),
            # idx_psx_ms_sym and idx_psx_ohlcv_sym_date were dropped by the
            # 20260714130000_db_integrity_cleanup migration as duplicates; assert
            # the surviving index of each pair (kept for the symbol/date reads).
            Check("psx_market_snapshot(symbol) index", "SELECT to_regclass('public.idx_psx_market_snapshot_symbol') IS NOT NULL"),
            # Asserted by SHAPE, not by index name. The real invariant is that
            # (symbol, date) reads are index-covered — which of the equivalent
            # indexes happens to provide that is an implementation detail.
            #
            # This previously named idx_psx_ohlcv_symbol_date_desc specifically.
            # That index is absent in production (20260712110000 is recorded as
            # applied and its sibling index exists, so this one failed or was
            # later dropped), yet the UNIQUE constraint index
            # psx_ohlcv_symbol_date_key already covers (symbol, date) — and
            # Postgres scans a btree backwards, so a separate DESC index buys
            # nothing. The name check therefore failed while the property it
            # was protecting held, and "fixing" it by creating the named index
            # would have added a redundant duplicate over ~1M rows.
            Check(
                "psx_ohlcv (symbol, date) reads are index-covered",
                """SELECT EXISTS (
                     SELECT 1 FROM pg_indexes
                     WHERE schemaname = 'public'
                       AND tablename = 'psx_ohlcv'
                       AND indexdef ~ 'USING btree \\(symbol, date'
                   )""",
            ),
            # idx_psx_alerts_user went with psx_alerts when it was dropped.
            Check("idx_psx_alerts_user index dropped", "SELECT to_regclass('public.idx_psx_alerts_user') IS NULL"),
            Check("RLS on psx_holdings", "SELECT relrowsecurity FROM pg_class WHERE relname='psx_holdings'"),
        ],
    ),
    MigrationCheck(
        filename="20260706130000_psx_realtime_and_fix.sql",
        description="Realtime + signals + watchlist v2 + price_alerts",
        checks=[
            Check("psx_signals table", "SELECT to_regclass('public.psx_signals') IS NOT NULL"),
            Check("user_watchlist table (v2)", "SELECT to_regclass('public.user_watchlist') IS NOT NULL"),
            Check("price_alerts table", "SELECT to_regclass('public.price_alerts') IS NOT NULL"),
            Check("psx_market_snapshot in supabase_realtime",
                  "SELECT 1 FROM pg_publication_tables "
                  "WHERE pubname='supabase_realtime' AND tablename='psx_market_snapshot'"),
            Check("psx_ticks REPLICA IDENTITY FULL",
                  "SELECT relreplident FROM pg_class WHERE relname='psx_ticks'"),
            Check("idx_user_watchlist_user index", "SELECT to_regclass('public.idx_user_watchlist_user') IS NOT NULL"),
            Check("idx_price_alerts_user index", "SELECT to_regclass('public.idx_price_alerts_user') IS NOT NULL"),
        ],
    ),
    MigrationCheck(
        filename="20260707100000_rls_with_check_fix.sql",
        description="Add WITH CHECK clauses to RLS policies",
        checks=[
            # psx_watchlist / psx_alerts WITH CHECK policies went with the v1
            # tables when 20260716050030_drop_v1_schema dropped them (2026-07-22).
            Check("psx_portfolios has WITH CHECK policy",
                  "SELECT with_check IS NOT NULL FROM pg_policies "
                  "WHERE schemaname='public' AND tablename='psx_portfolios'"),
            Check("psx_holdings has WITH CHECK policy",
                  "SELECT with_check IS NOT NULL FROM pg_policies "
                  "WHERE schemaname='public' AND tablename='psx_holdings'"),
        ],
    ),
    MigrationCheck(
        filename="20260708011922_add_idx_psx_portfolios_user_id.sql",
        description="Index on psx_portfolios.user_id",
        checks=[
            Check("idx_psx_portfolios_user_id index", "SELECT to_regclass('public.idx_psx_portfolios_user_id') IS NOT NULL"),
        ],
    ),
    MigrationCheck(
        filename="20260709010000_user_alerts_and_notifications.sql",
        description="user_alerts + in_app_notifications + prefs",
        checks=[
            Check("user_alerts table", "SELECT to_regclass('public.user_alerts') IS NOT NULL"),
            Check("in_app_notifications table", "SELECT to_regclass('public.in_app_notifications') IS NOT NULL"),
            Check("user_notification_prefs table", "SELECT to_regclass('public.user_notification_prefs') IS NOT NULL"),
            Check("idx_user_alerts_user index", "SELECT to_regclass('public.idx_user_alerts_user') IS NOT NULL"),
            Check("idx_in_app_notif_user index", "SELECT to_regclass('public.idx_in_app_notif_user') IS NOT NULL"),
            Check("RLS on user_alerts", "SELECT relrowsecurity FROM pg_class WHERE relname='user_alerts'"),
            Check("RLS on in_app_notifications", "SELECT relrowsecurity FROM pg_class WHERE relname='in_app_notifications'"),
            Check("RLS on user_notification_prefs", "SELECT relrowsecurity FROM pg_class WHERE relname='user_notification_prefs'"),
        ],
    ),
    MigrationCheck(
        filename="20260710000000_user_finance.sql",
        description="user_transactions + user_goals + user_budgets + user_bills + user_settings",
        checks=[
            Check("user_transactions table", "SELECT to_regclass('public.user_transactions') IS NOT NULL"),
            Check("user_goals table", "SELECT to_regclass('public.user_goals') IS NOT NULL"),
            Check("user_budgets table", "SELECT to_regclass('public.user_budgets') IS NOT NULL"),
            Check("user_bills table", "SELECT to_regclass('public.user_bills') IS NOT NULL"),
            Check("user_settings table", "SELECT to_regclass('public.user_settings') IS NOT NULL"),
            Check("user_transactions.amount column", "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='amount'"),
            Check("user_transactions.transaction_type column", "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='transaction_type'"),
            Check("user_goals.target column", "SELECT 1 FROM information_schema.columns WHERE table_name='user_goals' AND column_name='target'"),
            Check("user_budgets.limit_amount column", "SELECT 1 FROM information_schema.columns WHERE table_name='user_budgets' AND column_name='limit_amount'"),
            Check("user_bills.due_date column", "SELECT 1 FROM information_schema.columns WHERE table_name='user_bills' AND column_name='due_date'"),
            Check("user_settings.monthly_income column", "SELECT 1 FROM information_schema.columns WHERE table_name='user_settings' AND column_name='monthly_income'"),
            Check("RLS on user_transactions", "SELECT relrowsecurity FROM pg_class WHERE relname='user_transactions'"),
            Check("RLS on user_goals", "SELECT relrowsecurity FROM pg_class WHERE relname='user_goals'"),
            Check("RLS on user_budgets", "SELECT relrowsecurity FROM pg_class WHERE relname='user_budgets'"),
            Check("RLS on user_bills", "SELECT relrowsecurity FROM pg_class WHERE relname='user_bills'"),
            Check("RLS on user_settings", "SELECT relrowsecurity FROM pg_class WHERE relname='user_settings'"),
        ],
    ),
    MigrationCheck(
        filename="20260710010000_index_ohlcv.sql",
        description="Add OHLCV columns to psx_index_eod",
        checks=[
            Check("psx_index_eod.open column", "SELECT 1 FROM information_schema.columns WHERE table_name='psx_index_eod' AND column_name='open'"),
            Check("psx_index_eod.high column", "SELECT 1 FROM information_schema.columns WHERE table_name='psx_index_eod' AND column_name='high'"),
            Check("psx_index_eod.low column", "SELECT 1 FROM information_schema.columns WHERE table_name='psx_index_eod' AND column_name='low'"),
            Check("idx_psx_index_eod_code_date index", "SELECT to_regclass('public.idx_psx_index_eod_code_date') IS NOT NULL"),
            Check("psx_index_eod.open is NUMERIC",
                  "SELECT data_type='numeric' FROM information_schema.columns "
                  "WHERE table_name='psx_index_eod' AND column_name='open'"),
        ],
    ),
    MigrationCheck(
        filename="20260711000600_user_data_hardening_and_limits.sql",
        description="User table constraints and plan-limit triggers",
        checks=[
            Check("user_transactions FK to auth users",
                  "SELECT 1 FROM pg_constraint WHERE conname='user_transactions_user_id_fkey'"),
            Check("user_transactions amount positive",
                  "SELECT 1 FROM pg_constraint WHERE conname='user_transactions_amount_positive'"),
            Check("user_budgets unique category period",
                  "SELECT to_regclass('public.uq_user_budgets_user_category_period') IS NOT NULL"),
            Check("user_bills status check",
                  "SELECT 1 FROM pg_constraint WHERE conname='user_bills_status_check'"),
            Check("watchlist plan limit trigger",
                  "SELECT 1 FROM pg_trigger WHERE tgname='enforce_user_watchlist_plan_limit'"),
            Check("profile plan self-update trigger",
                  "SELECT 1 FROM pg_trigger WHERE tgname='prevent_profile_plan_self_update'"),
        ],
    ),
    MigrationCheck(
        filename="20260716000000_add_listed_in.sql",
        description="Add listed_in column to psx_profile",
        checks=[
            Check("psx_profile.listed_in column exists",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='psx_profile' AND column_name='listed_in'"),
        ],
    ),
    MigrationCheck(
        filename="20260721100000_psx_signals_v2.sql",
        description="Signals V2 explainable multi-horizon cache",
        checks=[
            Check("psx_signals_v2 table", "SELECT to_regclass('public.psx_signals_v2') IS NOT NULL"),
            Check("psx_signals_v2 symbol+horizon primary key",
                  "SELECT 1 FROM pg_constraint WHERE conname='psx_signals_v2_pkey'"),
            Check("idx_psx_signals_v2_rank_score index",
                  "SELECT to_regclass('public.idx_psx_signals_v2_rank_score') IS NOT NULL"),
        ],
    ),
    MigrationCheck(
        filename="20260716010000_apply_sector_map.sql (permanently disabled)",
        description="DPS owns psx_profile.sector; TV_SECTOR_MAP is the fallback only",
        checks=[
            # Was: "no raw TradingView sector may remain anywhere" — unachievable.
            # That assumed apply_sector_map would force every row to a mapped
            # value, but the migration is permanently disabled (its title-case
            # names would duplicate DPS's uppercase ones, and it maps Cement and
            # Fertilizer to "Textile"). job_refresh_fundamentals writes the real
            # PSX sector from DPS instead, and DPS simply has no company page for
            # a handful of symbols — those keep their old TV label forever, so
            # the old check could only ever fail.
            #
            # The real invariant: a raw TV sector is tolerable ONLY where DPS
            # gave us nothing (listed_shares IS NULL). If a symbol DPS *did*
            # classify shows up on a TV bucket, something overwrote good data —
            # which is exactly the bug fixed by making job_refresh_tv_data
            # preserve an existing sector instead of rewriting it every 5 min.
            # Detected by CASE rather than by an allow-list of the 18 mapped
            # TradingView buckets. DPS returns PSX's classification in upper
            # case ("COMMERCIAL BANKS", "OIL & GAS EXPLORATION COMPANIES");
            # every TradingView value is title case. Crucially, when TV returns
            # a sector TV_SECTOR_MAP has no entry for, the raw TV string is
            # stored as-is — so an allow-list of the 18 mapped names silently
            # misses those. That is exactly how MDTL sat on "Consumer Services"
            # while this check passed. Casing catches both paths.
            Check("No DPS-classified symbol has been reverted to a TradingView sector",
                  """SELECT (COUNT(*) FILTER (
                       WHERE listed_shares IS NOT NULL
                         AND sector IS NOT NULL
                         AND sector <> upper(sector)
                   ) = 0)::int FROM psx_profile"""),
        ],
    ),
    MigrationCheck(
        filename="20260716020000_mufap_performance_indexes.sql",
        description="MUFAP performance indexes",
        checks=[
            Check("psx_mutual_funds table exists",
                  "SELECT to_regclass('public.psx_mutual_funds') IS NOT NULL"),
            Check("psx_fund_nav_history table exists",
                  "SELECT to_regclass('public.psx_fund_nav_history') IS NOT NULL"),
            Check("idx_psx_mutual_funds_category index",
                  "SELECT to_regclass('public.idx_psx_mutual_funds_category') IS NOT NULL"),
            Check("idx_psx_fund_nav_history_fund_code index",
                  "SELECT to_regclass('public.idx_psx_fund_nav_history_fund_code') IS NOT NULL"),
            Check("idx_psx_fund_nav_history_date index",
                  "SELECT to_regclass('public.idx_psx_fund_nav_history_date') IS NOT NULL"),
        ],
    ),
    MigrationCheck(
        filename="20260716030000_tighten_grants.sql",
        description="Tighten grants to SELECT-only for anon/authenticated",
        checks=[
            Check("macro_rates table exists with RLS",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='macro_rates'"),
            Check("psx_news table exists with RLS",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='psx_news'"),
            Check("filings table exists with RLS",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='filings'"),
            Check("psx_unusual_activity table exists with RLS",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='psx_unusual_activity'"),
            Check("psx_financials_annual table exists with RLS",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='psx_financials_annual'"),
            Check("psx_financials_quarterly table exists with RLS",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='psx_financials_quarterly'"),
        ],
    ),
    MigrationCheck(
        filename="20260716050000_data_source_health.sql",
        description="Data source health table",
        checks=[
            Check("psx_data_source_health table exists",
                  "SELECT to_regclass('public.psx_data_source_health') IS NOT NULL"),
            Check("psx_data_source_health has RLS enabled",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='psx_data_source_health'"),
        ],
    ),
    MigrationCheck(
        filename="(stream-a) _applied_migrations ledger",
        description="Migration ledger from Stream A must be populated",
        checks=[
            Check("_applied_migrations ledger exists and has rows",
                  "SELECT (COUNT(*) > 0)::int FROM _applied_migrations"),
        ],
    ),
    MigrationCheck(
        filename="20260806140000_create_psx_intraday.sql",
        description="5-minute intraday bars backing the chart's 1D timeframe",
        checks=[
            Check("psx_intraday table exists",
                  "SELECT to_regclass('public.psx_intraday') IS NOT NULL"),
            Check("psx_intraday.session_date column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='psx_intraday' AND column_name='session_date'",
                  "The nightly prune filters on this; without it retention "
                  "never runs and the table grows by ~39k rows per session."),
            Check("psx_intraday.cum_volume column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='psx_intraday' AND column_name='cum_volume'"),
            Check("psx_intraday symbol+ts index",
                  "SELECT to_regclass('public.idx_psx_intraday_symbol_ts') IS NOT NULL"),
            Check("psx_intraday session_date index",
                  "SELECT to_regclass('public.idx_psx_intraday_session_date') IS NOT NULL"),
            Check("psx_intraday has RLS enabled",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='psx_intraday'"),
        ],
    ),
    MigrationCheck(
        filename="20260806170000_finance_opening_balance.sql",
        description="Opening balance anchoring the carried-forward finance balance",
        checks=[
            Check("user_settings.opening_balance column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='user_settings' AND column_name='opening_balance'",
                  "Without it finance.summary() cannot carry a balance across "
                  "months and every month silently restarts from zero."),
            Check("user_settings.opening_balance_date column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='user_settings' AND column_name='opening_balance_date'",
                  "Months strictly before this date are excluded from the running "
                  "total; without it they would double-count money already inside "
                  "the user's own opening figure."),
            Check("opening_balance defaults to 0 and is NOT NULL",
                  "SELECT (is_nullable='NO' AND column_default IS NOT NULL) "
                  "FROM information_schema.columns "
                  "WHERE table_name='user_settings' AND column_name='opening_balance'",
                  "A user who never sets one must keep the previous behaviour "
                  "(open at 0), not get NULL propagating through the summary."),
        ],
    ),
    MigrationCheck(
        filename="20260728120000_email_import_correlation.sql",
        description=(
            "Email-import correlation: staging ledger, learned merchant aliases, "
            "and the correlation/lifecycle columns on user_transactions."
        ),
        checks=[
            Check("email_import_messages table",
                  "SELECT to_regclass('public.email_import_messages') IS NOT NULL"),
            Check("email_merchant_aliases table",
                  "SELECT to_regclass('public.email_merchant_aliases') IS NOT NULL"),
            Check("email_import_messages unique on (user_id, message_id)",
                  "SELECT to_regclass('public.uq_email_import_messages_user_message') IS NOT NULL",
                  "Without it a re-poll re-stages the same email and the ledger "
                  "stops being an idempotency key."),
            Check("email_import_messages reconcile index",
                  "SELECT to_regclass('public.idx_email_import_messages_recon') IS NOT NULL"),
            Check("user_transactions.order_ref column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='order_ref'"),
            Check("user_transactions.account_tail column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='account_tail'"),
            Check("user_transactions.correlation_key column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='correlation_key'"),
            Check("user_transactions.reverses_transaction_id column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='reverses_transaction_id'"),
            Check("user_transactions.edited_at column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='user_transactions' AND column_name='edited_at'",
                  "The merge guard. Without it the reconciler cannot tell a "
                  "user-corrected row from an untouched import and could absorb it."),
            Check("user_bills.correlation_key column",
                  "SELECT 1 FROM information_schema.columns WHERE table_name='user_bills' AND column_name='correlation_key'"),
            Check("RLS on email_import_messages",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='email_import_messages'",
                  "Holds email subjects and parsed financial detail; must be "
                  "backend-only, like user_email_integrations."),
            Check("email_import_messages has NO policy for authenticated",
                  "SELECT NOT EXISTS (SELECT 1 FROM pg_policies "
                  "WHERE schemaname='public' AND tablename='email_import_messages')"),
            Check("RLS on email_merchant_aliases",
                  "SELECT relrowsecurity FROM pg_class WHERE relname='email_merchant_aliases'"),
        ],
    ),
    MigrationCheck(
        filename="20260716160000_ai_reports_shared_unique_nulls_restore.sql",
        description=(
            "Shared-report dedup index must treat NULL subjects as EQUAL. "
            "This has now been reverted once (20260716150000 re-keyed the index "
            "for lang and dropped NULLS NOT DISTINCT), which let three 'unique' "
            "market_brief rows coexist for one day and served the newest. There "
            "was no check here to catch it — that is why this one exists."
        ),
        checks=[
            Check(
                "shared unique index treats NULL subject as NOT DISTINCT",
                "SELECT 1 FROM pg_indexes WHERE tablename='ai_reports' "
                "AND indexname='uq_ai_reports_shared_subject_date_lang' "
                "AND indexdef ILIKE '%NULLS NOT DISTINCT%'",
                "Without this, market_brief (subject IS NULL) never dedupes and "
                "get_or_create_shared's ON CONFLICT silently does nothing.",
            ),
            Check(
                "no duplicate shared rows per (report_type, subject, date, lang)",
                "SELECT NOT EXISTS (SELECT 1 FROM ai_reports WHERE user_id IS NULL "
                "GROUP BY report_type, subject, trading_date, lang "
                "HAVING COUNT(*) > 1)",
                "Duplicates mean the index is not enforcing; the newest wins and "
                "shadows the real report.",
            ),
        ],
    ),
    MigrationCheck(
        filename="20260807100000_learnhub_lectures.sql",
        description="Admin-managed LearnHub lecture catalogue",
        checks=[
            Check(
                "learnhub_lectures table exists",
                "SELECT to_regclass('public.learnhub_lectures') IS NOT NULL",
            ),
            Check(
                "slug is unique",
                "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                "WHERE tablename = 'learnhub_lectures' AND indexdef ILIKE '%UNIQUE%slug%')",
                "Without this two lectures can claim the same /learn/lesson/$id route.",
            ),
            Check(
                "RLS is on",
                "SELECT relrowsecurity FROM pg_class WHERE relname = 'learnhub_lectures'",
                "Admin-managed tables are service_role only; a browser key must not read drafts.",
            ),
            Check(
                "learn permissions seeded",
                "SELECT COUNT(*) = 2 FROM public.admin_permissions "
                "WHERE slug IN ('learn.read', 'learn.write')",
            ),
            Check(
                "content_admin can manage lectures",
                "SELECT COUNT(*) = 2 FROM public.admin_role_permissions "
                "WHERE role_slug = 'content_admin' "
                "AND permission_slug IN ('learn.read', 'learn.write')",
            ),
            Check(
                "super_admin picked up the new permissions",
                "SELECT COUNT(*) = 2 FROM public.admin_role_permissions "
                "WHERE role_slug = 'super_admin' "
                "AND permission_slug IN ('learn.read', 'learn.write')",
                "The base migration seeds super_admin from a snapshot of the "
                "permission table, so a later permission needs re-seeding.",
            ),
        ],
    ),
]


@pytest.mark.asyncio
async def test_all_migrations_applied():
    """Verify required migrations are applied to Supabase.

    Runs every check in CHECKS against the live database. Fails if any check
    does not return a truthy result.
    """
    await ensure_reflected()
    engine = get_engine()
    failures: list[str] = []

    async with engine.connect() as conn:
        for mig in CHECKS:
            for chk in mig.checks:
                try:
                    r = await conn.execute(text(chk.sql))
                    row = r.first()
                    passed = bool(row and row[0])
                except Exception as e:
                    passed = False
                    failures.append(
                        f"  {mig.filename} :: {chk.name} -> EXCEPTION: {e}"
                    )
                    continue
                if not passed:
                    failures.append(f"  {mig.filename} :: {chk.name}")

    assert not failures, (
        f"Migration verification FAILED. {len(failures)} check(s) failed:\n"
        + "\n".join(failures)
    )
