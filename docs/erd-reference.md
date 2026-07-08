# NafaIQ — ERD Quick Reference

> **One-page reference for `docs/erd.md` (Mermaid) and `docs/erd.dbml` (DBML)**
> **Last updated:** 2026-07-07
> **Source of truth:** `supabase/migrations/*.sql`

---

## What is an ERD?

An **Entity-Relationship Diagram (ERD)** is a visual map of the database. It shows:

1. **Entities** (rectangles) — the tables in your database
2. **Attributes** (inside rectangles) — the columns
3. **Relationships** (lines) — how tables connect to each other
4. **Cardinalities** (symbols on the line ends) — how many of one thing relates to how many of another

---

## Project status

| Marker | Meaning |
|---|---|
| 🟢 **EXISTS** | Currently in `supabase/migrations/*.sql` (16 user-data tables) |
| 🟡 **PLANNED** | From `Complete Project Plan.md`, not yet migrated (24 tables) |
| 🔵 **LOGICAL** | Relationship enforced at app layer, not by SQL FK constraint |

### Existing tables (16)

```
auth.users              (Supabase managed)
profiles                (trigger-created)
psx_market_snapshot     ─┐
psx_ohlcv               │
psx_fundamentals        │
psx_profile             │  public read,
psx_announcements       │  service_role writes
psx_dividends           │
psx_index_eod           │
psx_ticks               │
psx_signals             ─┘

psx_watchlist (v1)      ─┐
psx_alerts (v1)         │  superseded,
user_watchlist (v2)     │  kept for backward compat
price_alerts (v2)       │
psx_portfolios          │  RLS: users see only their own
psx_holdings            ─┘
```

### Planned tables (24)

```
Phase 4: finance_accounts, finance_categories, finance_transactions,
         finance_budgets, finance_bills, finance_goals,
         finance_contributions, finance_zakat_calculations,
         user_notification_prefs, in_app_notifications, push_subscriptions
Phase 5: fx_rates
Phase 6: ai_usage, ai_chat_history, ai_reports
Phase 7: (additive columns on profiles: phone, mfa_enabled, onboarding_complete)
Phase 8: subscriptions, invoices, stripe_events, plan_features
Phase 9: audit_log, feature_flags, error_events
```

---

## Cardinality notation

### Mermaid / Crow's Foot (used in our diagram)

```
Symbol   Cardinality         Meaning
──────   ──────────          ───────
||       One (mandatory)     Every parent has exactly one child
o|       One (optional)      Parent may or may not have a child
}o / o{  Many (zero)         Zero or many of the child
}| / |{  Many (one+)         One or many of the child
```

Reading examples:
- `A ||--o{ B` means "One A has zero-or-many B" (1:N)
- `A }o--o{ B` means "Many A relate to many B" (M:N)
- `A ||--|| B` means "One A has exactly one B" (1:1)

### Crow's Foot symbol mapping

| Mermaid | Crow's Foot | Meaning |
|---|---|---|
| `\|\|` | `\|——\|` (one and only one) | Mandatory one |
| `o\|` | `○——\|` (zero or one) | Optional one |
| `}o` / `o{` | `>——○` (zero or many) | Many, optional |
| `}\|` / `\|{` | `>——\|` (one or many) | Many, mandatory |

### Chen notation (alternative)

```
A ────< B         means 1:N (A has many B)
A ────> B         means N:1
A ────<> B        means M:N
A ==============> B (double line) means 1:1 total
```

---

## How to read our ERD

### Example 1: `psx_portfolios ||--o{ psx_holdings`

```
[psx_portfolios] ||--o{ [psx_holdings]
```

This reads: **"Each portfolio contains zero or many holdings."**

- A user can have multiple portfolios
- Each portfolio can hold 0..N stocks
- Each holding belongs to exactly one portfolio
- The connecting column is `psx_holdings.portfolio_id` (FK, CASCADE)

### Example 2: `auth_users ||--o| profiles`

```
[auth_users] ||--o| [profiles]
```

This reads: **"Each user has zero or one profile."**

- Every user should have one profile (auto-created by `handle_new_user()` trigger)
- The `o|` indicates a brief race window before the trigger fires
- The connecting column is `profiles.id` (FK → `auth.users.id`)

### Example 3: `user_watchlist }o--|| psx_market_snapshot`

```
[user_watchlist] }o--|| [psx_market_snapshot]
```

This reads: **"Many watchlist entries reference exactly one stock."**

- One user can watch 0..N stocks
- Each watchlist entry points to exactly one symbol
- A symbol can appear in many users' watchlists (M:N mediated by `user_watchlist`)
- The connecting column is `user_watchlist.symbol` (⚠️ **logical, no FK declared in SQL**)

---

## Actual existing relationships

### FKs declared in SQL (8)

| Parent | → Child | Cascade |
|---|---|---|
| `auth.users` | `profiles` | CASCADE |
| `auth.users` | `psx_watchlist` (v1) | CASCADE |
| `auth.users` | `psx_alerts` (v1) | CASCADE |
| `auth.users` | `user_watchlist` (v2) | CASCADE |
| `auth.users` | `price_alerts` (v2) | CASCADE |
| `auth.users` | `psx_portfolios` | CASCADE |
| `psx_portfolios` | `psx_holdings` | CASCADE |

### Logical relationships (app-layer enforced, 🔵)

| Child | Joins via | Notes |
|---|---|---|
| `psx_ohlcv` | `symbol` | |
| `psx_fundamentals` | `symbol` (PK) | 1:1 with snapshot |
| `psx_profile` | `symbol` (PK) | 1:1 with snapshot |
| `psx_announcements` | `symbol` (nullable) | |
| `psx_dividends` | `symbol` | |
| `psx_ticks` | `symbol` | |
| `psx_signals` | `symbol` (PK) | 1:1 with snapshot |
| `psx_watchlist` (v1) | `symbol` | |
| `psx_alerts` (v1) | `symbol` | |
| `user_watchlist` (v2) | `symbol` | |
| `price_alerts` (v2) | `symbol` | |
| `psx_holdings` | `symbol` | |

> **Recommended:** Phase 1 cleanup should add explicit `FOREIGN KEY (symbol) REFERENCES psx_market_snapshot(symbol)` to all child tables.

---

## RLS policies (actual SQL)

| Group | Policy | Applies to |
|---|---|---|
| **Public read** | `USING (true)` to `anon, authenticated` | All `psx_*` market data tables |
| **User-owned** | `USING (auth.uid() = user_id)` | `profiles`, `psx_watchlist`, `psx_alerts`, `user_watchlist`, `price_alerts`, `psx_portfolios` |
| **Owned-via-parent** | `EXISTS (SELECT 1 FROM psx_portfolios WHERE id = psx_holdings.portfolio_id AND user_id = auth.uid())` | `psx_holdings` |

### RLS summary

**Public read, service_role writes** (PSX market data):
- `psx_market_snapshot`, `psx_ohlcv`, `psx_fundamentals`, `psx_profile`, `psx_announcements`, `psx_dividends`, `psx_index_eod`, `psx_ticks`, `psx_signals`

**Own data only (RLS)**:
- `profiles`, `psx_watchlist`, `psx_alerts`, `user_watchlist`, `price_alerts`, `psx_portfolios`, `psx_holdings`
- All planned `finance_*` tables
- All planned `ai_*` tables
- `user_notification_prefs`, `in_app_notifications`, `push_subscriptions`
- `subscriptions`, `invoices`

**Planned — service_role only (no RLS)**:
- `audit_log`, `stripe_events`, `error_events`, `feature_flags`

---

## CHECK constraints (actual SQL)

| Table | Constraint |
|---|---|
| `price_alerts` | `condition IN ('above','below','cross_above','cross_below')` |

> **Recommended Phase 1 add:** `psx_signals.signal IN ('STRONG BUY','BUY','HOLD','SELL','STRONG SELL')`

---

## Indexes (actual SQL)

| Table | Index | Purpose |
|---|---|---|
| `psx_market_snapshot` | `idx_psx_ms_sym(symbol)` | Symbol lookup |
| `psx_market_snapshot` | `idx_psx_ms_refreshed(refreshed_at DESC)` | Freshness check |
| `psx_ohlcv` | `idx_psx_ohlcv_sym_date(symbol, date)` UNIQUE | History + dedup |
| `psx_announcements` | `idx_psx_ann_sym(symbol, posted_at DESC)` | Per-symbol feed |
| `psx_announcements` | `idx_psx_ann_posted(posted_at DESC)` | Global feed |
| `psx_dividends` | `idx_psx_div_sym(symbol, ex_date DESC)` | Per-symbol dividends |
| `psx_index_eod` | `idx_psx_idx_code(code, date)` | Per-index history |
| `psx_ticks` | `idx_psx_tick_sym_time(symbol, time DESC)` | Tick chart |
| `psx_signals` | `idx_psx_signals_confidence(confidence DESC)` | Top signals |
| `psx_signals` | `idx_psx_signals_predicted(predicted_at DESC)` | Stale detection |
| `psx_alerts` (v1) | `idx_psx_alerts_user(user_id, symbol)` | Per-user alerts |
| `user_watchlist` (v2) | `idx_user_watchlist_user(user_id)` + UNIQUE(user_id, symbol) | Per-user watchlist |
| `price_alerts` (v2) | `idx_price_alerts_user(user_id)` + partial `idx_price_alerts_enabled(enabled) WHERE enabled` | Per-user + alert-check job |
| `psx_holdings` | UNIQUE(portfolio_id, symbol) | One row per (portfolio, symbol) |

---

## v1 vs v2 coexistence

Both versions of watchlist and alerts exist in the database today:

| Concept | v1 (legacy) | v2 (current) | Migration status |
|---|---|---|---|
| Watchlist | `psx_watchlist` (composite PK) | `user_watchlist` (bigint id) | Both tables exist; frontend uses v2 |
| Alerts | `psx_alerts` (type + condition + threshold) | `price_alerts` (condition + price, no `type`, CHECK on condition) | Both tables exist; `job_check_alerts` uses v2 |

**Recommendation:** Drop v1 tables in Phase 1 after confirming no other code path depends on them.

---

## How to render / share

| Format | File | Tool | Best for |
|---|---|---|---|
| Mermaid | `docs/erd.md` | GitHub, VS Code, Mermaid Live | Quick sharing, code review |
| DBML | `docs/erd.dbml` | dbdiagram.io | Interactive editing, exports to SQL/PNG |

To export to PNG/SVG:
- **Mermaid Live** (https://mermaid.live) — paste the mermaid block, download as PNG/SVG
- **dbdiagram.io** — paste the DBML, click "Export to PNG" or "Export to SQL"
