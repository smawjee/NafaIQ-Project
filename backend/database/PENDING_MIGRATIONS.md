# Pending migrations — live DB is behind this repo

Verified against the production Supabase project (`gmonfgxmjgzipnbhgimv`) on
**2026-07-15** by running `pytest tests/test_migrations_applied.py`.

Per `CLAUDE.md`, migrations are applied **via the Supabase Dashboard SQL Editor**.
Do not add an ad-hoc apply script — that creates a second, unreviewed path into
production. `scripts/apply_migrations_20260716.py` already drifted: its
hardcoded list omits every migration below, which is why they were never run.

## Live DB state at time of writing

| Fact | Value |
|---|---|
| `psx_ohlcv` | 973,599 rows · 836 symbols · 2016-07-11 → 2026-07-14 (~10y, intact) |
| `psx_profile` | 1,076 rows — **only 1** has `listed_shares` |
| `psx_watchlist` / `psx_alerts` (v1) | exist, **0 rows each** |
| `user_watchlist` / `price_alerts` (v2) | 17 / 3 rows — live |
| `_applied_migrations` | **does not exist** |
| `psx_data_source_health` sources | `announcement_pdfs`, `psx_announcements`, `refresh_dividends`, `tradingview`, `unusual_volume` |

## 1. `20260716050020_create_migration_ledger.sql` — NOT APPLIED

`_applied_migrations` does not exist. Safe and additive (one `CREATE TABLE` +
back-fill). Because it never ran, the file's back-fill lands clean — there is no
stale phantom row to reconcile.

**Action:** paste the file into the Dashboard SQL Editor and run it.

> The back-fill records **40 rows** — the migrations actually applied, not every
> file on disk. It deliberately omits the six unapplied files: `drop_v1_schema`
> (§2 below) and the five timestamped after it (`20260716060000`,
> `20260716070000`, `20260716120000`, `20260716130000`, `20260716140000`).
> **Apply the ledger BEFORE those five**, or its back-fill will understate
> reality. Each of the six needs a hand-written row when it is applied — see the
> INSERT snippet in the file header.

After it runs, `test_migrations_applied.py`'s ledger check goes green.

> Known gap: nothing writes to this table automatically. Until the apply flow
> INSERTs on each apply, new migrations must be recorded by hand or the ledger
> goes stale silently.

## 2. `20260716050030_drop_v1_schema.sql` — NOT APPLIED

Drops `psx_watchlist` + `psx_alerts`. **Confirmed safe:** both hold 0 rows, no
code references them (`grep` over `backend/src` and `frontend/.../src` is
clean), and the v2 tables have taken over.

Destructive and irreversible, so it is left for a deliberate run.

**When you apply it, in the same change:**

1. In `tests/test_migrations_applied.py`, flip these three back to `IS NULL`:
   - `psx_watchlist table (v1)`
   - `psx_alerts table (v1)`
   - `idx_psx_alerts_user index`
2. **Remove** these two checks under `20260707100000_rls_with_check_fix.sql` —
   they query `pg_policies` for the dropped tables and will start failing:
   - `psx_watchlist has WITH CHECK policy`
   - `psx_alerts has WITH CHECK policy`

## 3. `20260716010000_apply_sector_map.sql.disabled` — DISABLED, but its test still asserts the end state

The file is disabled on the rationale that the scheduler normalizes sectors via
`TV_SECTOR_MAP` at write time. **The live DB contradicts that:** raw TradingView
sector values still remain in `psx_profile`, so the check
`No raw TradingView sector inputs remain in psx_profile` fails.

Write-time mapping only touches rows the TV job upserts; `psx_profile` has 1,076
rows while the TV feed covers ~500, so the remainder keep their raw sector.

**Consequence:** raw (`Finance`) and mapped (`BANKING & FINANCE`) values coexist,
which **splits one sector into two buckets in the treemap/heatmap**.

**Decide one:**
- re-enable + apply the migration (back-fills old rows), or
- drop the test check and accept the split.

Leaving it as-is keeps the suite red and the heatmap fragmented.

## 4. `refresh_fundamentals` has never run — the real cause of missing market caps

It is **absent from `psx_data_source_health`**, and only 1 of 1,076 profiles has
`listed_shares`. It is the **sole writer** of that column (`job_refresh_tv_data`
only *preserves* existing values), so real market cap cannot be computed and the
treemap's `volume_proxy` is permanent, not transitional.

The schedule was also wrong: timezone-naive (fired on host local time) and
`day_of_week=6` — **Sunday** in APScheduler — despite being documented as
"weekly Sat 04:00". Now pinned to `Asia/Karachi` / `day_of_week="sat"`.

That fix alone is not enough: if the backend isn't running at 04:00 PKT on a
Saturday, it still never fires. **It needs one deliberate manual run** to
populate `listed_shares`. It is a heavy scrape (~1,076 symbols against DPS), so
it should not be a startup warm-start.

Once it succeeds, real market caps light up across the treemap and screener, and
`sizing_basis` flips from `volume_proxy` to `market_cap` on its own.

## 5. Migrations added after this doc was first written — all NOT APPLIED

Apply in timestamp order, **after** the ledger (§1) so its back-fill stays accurate.
Each needs a hand-written `_applied_migrations` row once run.

| File | What it does | Notes before applying |
|---|---|---|
| `20260716060000_cleanup_duplicates_and_orphans.sql` | drops dup indexes, guarded orphan cleanup, OHLCV repair | §1 of the file drops `psx_index_eod_unique`, an object no tracked migration creates. It now branches on constraint-vs-index and no-ops if absent. Run `\d psx_index_eod` first if you want to know which branch fires. |
| `20260716070000_analyze_and_refresh.sql` | ANALYZE + refresh | — |
| `20260716120000_ai_reports_lang.sql` | adds `ai_reports.lang`, re-keys the report cache | Back-fills existing rows to `'en'`. |
| `20260716130000_health_column_grants.sql` | **SECURITY**: revokes table-wide SELECT on `psx_data_source_health` from `anon, authenticated`, re-grants per column without `last_error_message` | Closes direct PostgREST read of raw `str(e)` text via the public anon key. Backend uses `service_key`, so `/health/sources` is unaffected. After this, `?select=*` fails for anon by design — name columns explicitly. |
| `20260716140000_ohlcv_date_symbol_index.sql` | adds `(date, symbol) INCLUDE (volume)` on `psx_ohlcv` for the volume-spike scan | ⚠️ **`CREATE INDEX CONCURRENTLY` cannot run inside a transaction.** Paste the single statement into an empty editor tab and run it alone — do not bundle it. ~973k rows, so the build takes a moment; verify `indisvalid` afterwards and drop/retry if it came out INVALID. |
| `20260716160000_ai_reports_shared_unique_nulls_restore.sql` | **restores `NULLS NOT DISTINCT`** on the shared unique index and purges duplicates. Drops BOTH old/new index names so it works whether or not `20260716150000` (the regression) was applied. Also ensures `lang` column exists. | ⚠️ **Apply this to fix the Market Brief.** Replaces the need for `20260716150000` entirely — this one migration does the combined work of adding `lang`, deleting duplicates, and creating the correct index with `NULLS NOT DISTINCT`. Run this INSTEAD of `20260716150000`. |
