# Admin Dashboard — Operations & Security Guide

The admin dashboard is NafaIQ's operations console. Access is controlled by a
database-backed RBAC model and enforced **server-side on every request**. This
guide covers granting/revoking access, how permissions and audit work, feature
flags, migrations, deployment, and troubleshooting.

> Security first: never grant admin by editing the browser, local storage, or a
> hard-coded email. Admin access exists only as rows in `admin_role_assignments`,
> which browsers cannot read or write (RLS deny-all; service_role only).

## Concepts

- **Roles** (`admin_roles`): `super_admin`, `support_admin`, `finance_admin`,
  `data_admin`, `ai_admin`, `content_admin`, `analyst_readonly`. A user may hold
  several.
- **Permissions** (`admin_permissions`): fine-grained slugs (e.g. `users.suspend`,
  `flags.write`, `audit.read`). Roles map to permissions in
  `admin_role_permissions`. `super_admin` implicitly holds every permission.

  Every seeded permission has a route behind it. `users.delete` and
  `subscriptions.write` were removed in
  `20260728090000_admin_alerts_and_dead_permissions.sql` because nothing
  implemented them — a permission that grants no capability is misleading on the
  Roles screen. If you add a permission, add its endpoint in the same change.
- **Assignments** (`admin_role_assignments`): active while `revoked_at IS NULL`;
  revoked rows are kept for history.
- **Audit** (`admin_audit_log`): append-only (a DB trigger blocks UPDATE/DELETE).
  Every mutation records actor, roles, action, resource, target, before/after,
  reason, request id, IP, status, and timestamp.
- **Account status** (`profiles.account_status`): `active` | `suspended` |
  `restricted`. `suspended` is rejected at the identity boundary
  (`services/auth.py`), so a suspended user is blocked from every authenticated
  route at once.

## Granting the FIRST administrator (bootstrap)

No admin can exist before the first one, so the first is created from operator-
controlled environment configuration — not from the UI.

1. Ensure the person already has a NafaIQ account (they must exist in Supabase
   `auth.users`).
2. In `backend/.env` set:
   ```
   ADMIN_BOOTSTRAP_EMAILS=you@example.com,teammate@example.com
   ```
3. Start the backend. On startup, **only if no active super_admin exists**, each
   listed email that matches an existing user is granted `super_admin`, and a
   `system:bootstrap` row is written to the audit log. The step is idempotent and
   self-disabling: once any super_admin exists it never runs again, so the env
   var can be left in place.
4. Verify: sign in as that user — the sidebar shows **Admin** and `/admin` loads.

## Granting / revoking access after bootstrap

Use the UI (a `super_admin` can assign roles from a user's profile page), or the
CLI:

```bash
cd backend
python -m scripts.grant_admin list                     # show current admins
python -m scripts.grant_admin grant  user@x.com support_admin
python -m scripts.grant_admin revoke user@x.com support_admin
```

Guardrails enforced everywhere (UI, API, CLI):
- Only a `super_admin` may assign or revoke `super_admin`.
- A non-super admin may only grant a role whose permissions are a subset of their
  own (no privilege escalation).
- The **last active `super_admin` cannot be revoked**.

## Revoking admin access

Revoke each role from the user's profile page, or
`python -m scripts.grant_admin revoke <email> <role>`. Revocation is recorded in
the audit log. To fully lock a person out of the product, suspend their account
(Users → user → Suspend), which blocks all authenticated access immediately.

## Feature flags

`platform_flags` holds typed, validated switches (bool/int/string/enum). Edits go
through `PUT /api/admin/flags/{key}` (`flags.write`), are type-checked server-side,
and are audited. This is **not** a free-form key/value store — a value that
doesn't match the flag's declared type is rejected.

### How a flag actually takes effect

`app/services/flags.py` is the read side. It caches a snapshot of the whole table
for **15 seconds**, so:

- A flag lookup costs no database round-trip on the hot path.
- After an edit, every web process honours the new value within 15s. The process
  that served the write calls `flags.invalidate()`, so it is immediate there.
- Lookups **fail open**: if the flag store is unreachable, callers get their
  declared default. The flags exist to disable features deliberately, not to
  become a new hard dependency.
- A row with `enabled = false` is treated as *unconfigured* — the caller's
  default wins. That retires a flag without deleting it or changing behaviour.

### Where each flag is enforced

| Flag | Enforcement point | Effect when off |
| --- | --- | --- |
| `maintenance_mode` | `_maintenance_mode` middleware in `main.py` | Whole API returns 503 + `Retry-After: 300`. Exempt: `/api/health`, `/api/admin`, `/api/platform`, `/docs`, `/openapi.json` — so an admin can still reach the console to switch it back off. |
| `signals_enabled` | router dependency on `signals` + `signals_v4` | `/api/signals*` returns 503. |
| `ai_features_enabled` | router dependency on `ai`, `learn_ai`; master switch for `assistant`/`reports` | All AI routes return 503. |
| `assistant_enabled` | router dependency on `assistant` (also requires `ai_features_enabled`) | `/api/assistant*` returns 503. |
| `reports_enabled` | router dependency on `reports` (also requires `ai_features_enabled`) | `/api/reports*` returns 503. |
| `registration_enabled` | **client-side only** — see below | Sign-up UI hides/blocks. |

503 is used rather than 403 on purpose: the caller *is* authorized, the
capability is temporarily unavailable, and clients should treat it as retryable.

### `registration_enabled` is not a server-side gate

Sign-up goes directly from the browser to Supabase Auth; it never transits this
backend, so there is no request for the API to reject. The flag is exposed on
the anonymous `GET /api/platform/flags` endpoint (alongside `maintenance_mode`)
for the web/mobile app to read and render against. **Treat it as a UI switch,
not an access control.** To hard-close registration, disable sign-ups in the
Supabase Auth settings.

`GET /api/platform/flags` returns only an allow-listed subset
(`flags.public_flags()`); no other flag is ever exposed anonymously.

## Audit log

`/admin/audit` (permission `audit.read`) is paginated and filterable by:

- `action` — **substring, case-insensitive** match, so `user` finds
  `admin.user.tier` and `admin.user.status`. `%` and `_` in the input are
  escaped, so a stray wildcard can't widen the query.
- `status` — `success` / `failure`
- `actor_user_id`, `target_user_id`
- `since` / `until` — ISO 8601 bounds on `created_at`, backing the console's
  date-range filter.

Entries are immutable — the table blocks UPDATE/DELETE at the database
level, so the trail cannot be rewritten, even by the backend.

## Operational actions

`POST /api/admin/market-data/refresh` (permission `market_data.refresh`) runs the
market-watch ingest immediately instead of waiting for the 10-second cron tick.
It is idempotent (the write is an upsert keyed on `symbol`) and audited with the
row count it produced, so the log distinguishes a real refresh from an empty one.
Unlike the cron job it does **not** apply the market-hours guard — an admin
asking for a refresh out of hours wants the latest available figures, not a
silent no-op.

`GET /api/admin/alerts` (permission `alerts.read`) reports platform-wide alert
volume and delivery health. Aggregates only — the contents of an individual
user's alerts are never exposed to the console.

## Migrations

```bash
cd backend
python -m scripts.apply_admin_migrations   # applies 20260727120000_admin_dashboard.sql
```

The migration is non-destructive and re-runnable. Rollback SQL is documented in
`backend/database/PENDING_MIGRATIONS.md`.

## Required environment variables

- `ADMIN_BOOTSTRAP_EMAILS` (backend, optional) — comma-separated emails for the
  first-admin claim. Leave blank once an admin exists.
- Existing DB/auth vars are reused: `SUPABASE_URL`, `SUPABASE_JWT_SECRET`,
  `SUPABASE_DATABASE_PASSWORD`, `SUPABASE_POOLER_*`. No new secret is introduced,
  and nothing admin-related is exposed to the browser.

## Deployment

1. Apply the migration to the target Supabase project (`apply_admin_migrations`).
2. Deploy the backend (Railway) and the web app as usual.
3. Set `ADMIN_BOOTSTRAP_EMAILS` on the backend service for the first environment,
   restart, confirm the audit row, then clear or leave the var.

## Troubleshooting

- **`/admin` redirects me to the app** — you have no active admin role. Confirm
  with `grant_admin list`; check the account isn't suspended.
- **`GET /api/admin/me` returns 403** — same cause; the server found no roles for
  your user id. RBAC is DB-backed, so a client tweak can't change this.
- **Bootstrap didn't grant** — the email didn't match an existing `auth.users`
  row, or a super_admin already existed (bootstrap self-disables). Check the
  backend logs for `admin_bootstrap:*`.
- **A metric shows "Not tracked yet / unavailable"** — that block's query failed
  or the metric isn't computed; the UI never fabricates a number.
- **Can't revoke the last super_admin** — by design. Grant super_admin to another
  trusted user first.

## Security notes

- Admin authorization is enforced on the server for every action; the frontend
  guard only decides what to render.
- The Supabase service-role key and all provider API keys stay backend-only.
- AI operations show usage/metadata only — never raw keys or user conversations.
- Destructive actions require confirmation and are audited with before/after
  state and a reason.

## Known gap: the `restricted` account status

`profiles.account_status` accepts `active | suspended | restricted`, and the
console displays and filters all three. But **only `suspended` is enforced** —
`services/auth.py` rejects suspended users and explicitly treats `restricted` as
"reserved for future partial limits".

The console therefore offers **no "Restrict" action**. Adding one would let an
administrator believe they had limited an account when nothing would change.
If partial restriction is wanted, decide what it means (read-only? no AI? no
trading actions?), enforce it in `services/auth.py` alongside the suspended
check, and only then add the control.

A `restricted` value set directly in the database still renders correctly
everywhere in the console.

## Console UI notes

- **Theme and language** are switchable from inside the console (header, right
  side). Both write to the same stores the main app uses (`nafaiq-landing-theme`,
  `nafaiq-app-lang`), so the preference carries across.
- Urdu switches the console to RTL via a `dir` attribute on the console root.
  Every layout rule uses logical properties, so the whole thing mirrors.
  **Identifiers are never translated** — permission slugs, flag keys, audit
  action codes and DB column names stay in English because they are the literal
  values stored server-side.
- While the console is mounted it sets `data-admin-console` on `<html>`. That is
  what lets the console's palette reach *portalled* surfaces — the toast
  container and the shared confirm dialog are mounted once at the app root,
  outside the console's DOM subtree.

## Plan entitlements

`plan_features` is **live configuration, not a static lookup**. Every column is
read on the request path by `repositories/user_repo.py:get_plan_features` and
enforces a real limit (watchlist caps, AI tutor/report quotas, per-plan feature
flags). It is **uncached**, so an edit applies from the very next request — there
is no cache to bust and no restart needed.

- `GET /api/admin/plans` — `subscriptions.read`
- `PUT /api/admin/plans/{plan}` — `subscriptions.write`

The writable surface is pinned in `repositories/admin/plans_repo.py`
(`EDITABLE_COLUMNS`); the UPDATE statement is built from that tuple, never from
request keys, because column names can't be bound parameters. `plan` and `rank`
are deliberately **not** editable — `plan` is the row identity, and `rank` orders
upgrade comparisons elsewhere in the backend.

Validation (`services/admin/plans.py`) rejects rather than coerces: negatives,
`bool` where an int is expected (bool subclasses int), ints where a bool is
expected, `null` on a NOT NULL column, and out-of-set enum values. `null` is
meaningful on `ai_tutor_daily_limit` / `ai_reports_per_period` — it means *no
limit*. Each edit writes one `admin.plan.update` audit row containing only the
keys that actually changed.

> `subscriptions.write` was removed by `20260728090000_*` as a permission with no
> endpoint, then restored by `20260728150000_*` once the endpoint existed. The
> capability was always real; only the route was missing.

## User lifecycle actions

Backed by the Supabase Auth admin API (`services/admin/user_ops.py`). All audited.

| Action | Route | Permission |
| --- | --- | --- |
| Force sign-out | `POST /api/admin/users/{id}/sign-out` | `users.suspend` |
| Send password reset | `POST /api/admin/users/{id}/password-reset` | `users.suspend` |
| Resend verification | `POST /api/admin/users/{id}/resend-verification` | `users.suspend` |
| Anonymise | `POST /api/admin/users/{id}/anonymise` | `users.anonymise` (super_admin only) |

**Recovery links never leave the backend.** `generate_link`-style flows return a
live, single-use URL that grants control of the account. Returning it to the
caller — or logging it, or putting it in the audit row — would turn
`users.suspend` into an account-takeover primitive: any support admin could mint
a link for any account, including a super admin's. The endpoint sends the mail
and returns only a status. Enforced by a test.

Force sign-out complements suspension rather than duplicating it: suspension is
checked when the next request arrives, while this revokes the refresh tokens so
no new access token can be minted at all.

### Anonymisation semantics

Identity is destroyed; activity is kept.

1. `auth.users.email` → `deleted-<8hex>@anonymised.invalid` (`.invalid` is
   reserved by RFC 2606, so it can never route or be re-registered).
2. `profiles.display_name` → NULL, account suspended with a reason.
3. All sessions revoked.
4. **Portfolios, holdings, transactions and finance rows are kept**, so platform
   aggregates and the audit trail stay truthful.

The audit row stores only a redacted address (`u***@e***.com`) — the log is
readable by every `audit.read` holder, so it must not become the one place the
original address survives. Irreversible, so the UI requires the admin to retype
the email rather than click a one-step confirm.

Not implemented: **hard delete**. `auth.admin.delete_user` cascades and destroys
the user's activity along with their identity; anonymisation satisfies erasure
requests without falsifying historical aggregates.

## URL-persisted table state

Every admin list screen keeps its filters, sort and page in the route's search
params (`routes/admin.*.tsx` `validateSearch` + `features/admin/data/tableSearch.ts`).
A filtered view is therefore shareable, survives a refresh, and steps correctly
with browser back/forward.

Two rules worth knowing before adding a screen:

- **Search params are attacker-controlled.** `validateSearch` runs on every
  navigation including a hand-edited URL, so it clamps and falls back — it never
  throws. Sort keys mirror the server's own whitelist.
- **Every field is optional and defaults are applied in the page,** not in the
  validator. `/admin/users/$userId` is a *child* of `/admin/users` and inherits
  its schema; required fields there would force every `<Link>` to a user profile
  to restate the whole filter set. It also keeps shared URLs clean.

## Error tracking

Before this existed there was **no way to know a user hit a bug**: the frontend
ErrorBoundary only `console.error`'d, backend exceptions went to stdout (ephemeral
on Railway, not queryable, not per-user), and no error-tracking SDK was installed.

Capture is self-hosted in Supabase rather than an external service.

**What is captured**

| Path | Source |
| --- | --- |
| React render crashes | `ErrorBoundary.componentDidCatch` |
| Event handlers, async callbacks, rejected promises | `window.onerror` / `unhandledrejection` (`lib/telemetry.ts`) |
| Unhandled server exceptions and handled 5xx | `_capture_server_errors` middleware in `main.py` |

**503 is deliberately excluded.** In this app every 503 is intentional — the
maintenance middleware and the feature-flag gates both return it to mean
"switched off on purpose". Recording those would fill the tracker with the
operator's own decisions and bury the real 500s.

**Grouping.** `services/telemetry.py:fingerprint` hashes
`source | normalised message | route | first app stack frame`. Numbers and UUIDs
are normalised out, so "User 123 not found" and "User 456 not found" are one bug;
line/column numbers are stripped so an edit above the throw doesn't split the
group; vendor frames are skipped because bundled paths shift every build. Route
*is* part of the key — the same exception from two screens is usually two fixes.

**PII.** Emails, UUIDs, JWTs and API keys are replaced on the way IN, not on the
way out — this table is readable by every `errors.read` holder. Query strings are
stripped from routes. Request bodies and headers are never stored.

**Volume.** 20 events per caller per minute (the group counter still advances, so
the admin still sees it happening), plus client-side de-dup, plus a 30-day
retention sweep (`job_purge_error_events`, daily 04:15 PKT).

**Fail-safety.** `capture_error` never raises — it runs on the failure path, so an
exception there would turn a handled error into a broken response. It also no-ops
under pytest, so the suite can't write test noise into the live tracker.

**Resolved is not final.** If a fingerprint marked resolved is captured again,
ingest re-opens the group. An error that recurs was not fixed.

Routes: `GET/PATCH /api/admin/errors*` (`errors.read` / `errors.write`),
`GET /api/admin/users/{id}/errors` (per-user, shown on the profile page),
and the anonymous `POST /api/telemetry/errors` ingest.

## Bug reports

Automatic capture yields a stack trace; it never says what the user was trying to
do. Data bugs — "my portfolio total is wrong" — throw no exception at all and are
otherwise invisible.

Users file from the lifebuoy icon in the app header. Route and app version are
attached automatically, which removes the "which page were you on?" round-trip.
Reporters see their own reports and the admin's reply in the same dialog — a
reporter who never hears back stops reporting.

Admin queue at `/admin/bug-reports` (`support.read` / `support.write`): filter by
status and category, read the report with its context, reply and set status. RLS
lets a user read and insert **their own** rows only; there is deliberately no
update policy, so a filed report can't be edited or self-triaged.

