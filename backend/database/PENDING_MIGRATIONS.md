# Pending migrations — status

Reconciled against the production Supabase project (`gmonfgxmjgzipnbhgimv`) on
**2026-07-22**. The `_applied_migrations` ledger was brought back in sync this
day: every migration proven-applied against live DB objects now has a ledger
row, and each new migration records itself (see the footer in any file dated
2026-07-22+).

## Pending 2026-07-27 (admin dashboard)

| Migration | What it does | Apply with |
|---|---|---|
| `20260727120000_admin_dashboard.sql` | Adds the admin RBAC model (`admin_roles`, `admin_permissions`, `admin_role_permissions`, `admin_role_assignments`), append-only `admin_audit_log` (UPDATE/DELETE-blocking trigger), `admin_user_notes`, typed `platform_flags`, and `profiles.account_status`/`status_reason`/`status_changed_at`/`status_changed_by`. All admin tables get RLS deny-all for anon/authenticated + service_role-only grants. Seeds roles, permissions, mappings, and starter flags. NON-DESTRUCTIVE. | `python -m scripts.apply_admin_migrations` |

Rollback (if ever needed): `DROP TABLE public.admin_audit_log, public.admin_user_notes, public.admin_role_permissions, public.admin_role_assignments, public.admin_roles, public.admin_permissions, public.platform_flags CASCADE;` then `ALTER TABLE public.profiles DROP COLUMN account_status, DROP COLUMN status_reason, DROP COLUMN status_changed_at, DROP COLUMN status_changed_by;`. No existing table is modified destructively by the migration.

## Applied 2026-07-22 (this remediation)

| Migration | What it did |
|---|---|
| `20260716050030_drop_v1_schema.sql` | Dropped the dead v1 `psx_watchlist` / `psx_alerts` (0 rows, no code refs). |
| `20260722110000_backfill_holdings_opening_lots.sql` | Opening lots for 4 holdings with no backing transactions. |
| `20260722110100_reconcile_cnergy_drift.sql` | Reconciled the CNERGY holding drift in portfolio 19. |
| `20260722120000_finance_integrity.sql` | Resynced every `user_budgets.spent`; corrected the future-dated txn; added the future-date trigger. |
| `20260722130000_ohlcv_is_adjusted_honesty.sql` | Corrected the misleading `is_adjusted` flag on 976k rows (flag only — no prices touched). |
| `20260722140000_tighten_grants_all_tables.sql` | Revoked default write/TRUNCATE grants from anon/authenticated on 49 tables; SELECT preserved. |
| `20260722150000_filings_announcement_fk.sql` | Added the missing `filings → psx_announcements` FK. |
| `20260722160000_reconcile_plan_columns.sql` | Synced the 2 stale `user_settings.plan` copies to authoritative `profiles.plan`. |

Also recorded in the ledger (were applied earlier but never recorded):
`20260716150000_ai_reports_shared_lang_unique`,
`20260716160000_ai_reports_shared_unique_nulls_restore`,
`20260717210000_canonicalize_finance_categories`,
`20260717220000_consolidate_legacy_categories`,
`20260721100000_psx_signals_v2`.

## Deliberately NOT applied

### `20260716060000_cleanup_duplicates_and_orphans.sql` — DO NOT APPLY AS-IS

Two sections are unsafe against the current live DB:

- **§3 deletes "orphan" `psx_market_snapshot` rows** whose symbol is absent from
  `psx_profile`. Those 47 rows were verified on 2026-07-22 to be **legitimate
  live quotes** for transient instrument classes (`*NC`, `*XD`, `*ETFXD`, `*WU`,
  `*XB`) that trade but are not in the DPS company catalogue. Deleting them
  removes real market data.
- **§4 rewrites 41,393 OHLCV bars** to force `close` inside `[low, high]`. Those
  bars are **not corrupt** — they are PSX LDCP (last-day-close) semantics for
  illiquid scrips (96% have `close = prior close`; 0 blue chips affected). The
  standing rule is: never delete or rewrite historical PSX market data.

If any part of this file is ever wanted, extract only the duplicate-index drops
(§1–§2) into a fresh migration and leave §3–§4 out.

### `20260716010000_apply_sector_map.sql.disabled` — sector taxonomy (deferred)

The `psx_profile.sector` column mixes DPS and raw TradingView taxonomies. Unifying
them is a deliberate product decision that is **deferred** — sector data is not to
be touched for now. `test_migrations_applied.py`'s sector check consequently stays
red; that is the single known-red check and is not a regression.

## Known follow-ups (not migrations)

- **Deploy the branch.** The scraper/scheduler fixes (dividends, announcements,
  shariah, OHLCV coverage, SBP macro) are verified working locally but live only
  in the working tree — production still runs the old code and keeps re-failing
  those jobs until deployed.
- **SBP FX endpoint** returns no USD/PKR table at any known path; the FX feed is
  the one macro series still empty and needs endpoint rediscovery.
- **Regenerate frontend Supabase types** — they still list the dropped v1 tables
  (harmless, unused). Runs on the team's normal `supabase gen types` flow.
