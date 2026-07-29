# NafaIQ Admin Dashboard — Implementation Plan & Status

**Status:** First pass delivered — secure foundation + core modules, built and verified.
**Scope this pass:** RBAC + server-side authz, admin shell, Overview, Users, Roles/Access, Subscriptions, Audit, Feature Flags, and read-only Market-Data / Signals / AI / System monitoring. Impersonation, support tooling, content CRUD, and notification broadcasts are deferred with extension points.

---

## 1. Repository findings (audit)

- **No prior admin surface.** The only pre-existing "admin" was the backend-only `PSX_ADMIN_TOKEN` gating `/api/funds/import` (`backend/src/app/middleware/auth.py`). All user authorization was **tier-based** (`profiles.plan` ∈ Free/Pro/Premium via `plan_features`, `services/permissions.py`). No role/permission model, no audit log, no account status existed.
- **Identity:** Supabase JWT → `services/auth.py:resolve_supabase_user()` → `{user_id, email, plan, features}`; dep `api/deps.py:require_user`.
- **DB:** two paths — PostgREST (`db/supabase.py`, scrapers) and **SQLAlchemy async via the pooler** (`db/sqlalchemy.py`, `repositories/base.py`). Admin uses the SQLAlchemy path, the privileged role that can reach RLS-denied tables.
- **Migrations:** raw SQL in `backend/database/migrations/`, applied out-of-band via `scripts/apply_*_migration.py` + `_applied_migrations` ledger.
- **Reused ops data (no new ingestion):** `psx_data_source_health`, `psx_index_live_snapshot`, `psx_signal_model_registry`, `assistant_usage`, `learnhub_ai_usage`, `ai_reports`.
- **Frontend:** TanStack Start flat routes, `hooks/use-auth.tsx`, gate in `routes/__root.tsx`, API client `lib/psx/client.ts` (`userGet/userPost/...`). Mostly custom shared components + Tailwind (limited shadcn set).

## 2. Architecture delivered

**Principle:** identity from the JWT; **admin roles/permissions resolved server-side from the DB on every call** — never trusted from the client. Frontend guards are UX only.

- **RBAC:** `admin_roles`, `admin_permissions`, `admin_role_permissions`, `admin_role_assignments` (active = `revoked_at IS NULL`). 7 seeded roles, 20 permission slugs. `super_admin` implicitly holds all.
- **Audit:** `admin_audit_log`, append-only (BEFORE UPDATE/DELETE trigger raises). Records actor, roles, action, resource, target, before/after, reason, request_id, ip, status, timestamp.
- **Flags:** `platform_flags` (typed: bool/int/string/enum, validated server-side).
- **Account status:** `profiles.account_status` (+ reason/changed_at/changed_by); `suspended` is rejected at the identity boundary.
- **RLS:** every admin table is RLS-enabled with **no anon/authenticated policy** (deny-all) and service_role-only grants → browsers can't read or self-grant.

## 3. Role & permission model

| Role | Permissions (summary) |
|---|---|
| `super_admin` | Everything (implicit + fully seeded) |
| `support_admin` | overview.read, users.read/note/suspend, users.tier.read, audit.read, system.read |
| `finance_admin` | overview.read, users.read, users.tier.read/write, subscriptions.read/write, audit.read |
| `data_admin` | overview.read, market_data.read/refresh, signals.read, system.read, audit.read |
| `ai_admin` | overview.read, ai.read, flags.read/write, audit.read, system.read |
| `content_admin` | overview.read, audit.read, system.read (content CRUD deferred) |
| `analyst_readonly` | every `*.read` |

**Escalation guards:** only `super_admin` assigns/revokes `super_admin`; a non-super admin can only grant a role whose permissions ⊆ their own; the **last active super_admin cannot be revoked**.

## 4. Database migrations added

- `backend/database/migrations/20260727120000_admin_dashboard.sql` — all tables/columns/RLS/seeds above. Non-destructive (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS / ON CONFLICT). Self-records in the ledger.
- Apply: `cd backend && python -m scripts.apply_admin_migrations`
- Rollback documented in `backend/database/PENDING_MIGRATIONS.md`.

## 5. API endpoints added (`/api/admin/*`, JWT + per-route permission)

`GET /me` · `GET /overview` · `GET /users` · `GET /users/{id}` · `GET /users/{id}/roles` · `POST /users/{id}/status` · `POST /users/{id}/tier` · `POST /users/{id}/notes` · `POST /users/{id}/roles` · `DELETE /users/{id}/roles/{slug}` · `GET /roles` · `GET /permissions` · `GET /admins` · `GET /flags` · `PUT /flags/{key}` · `GET /audit` · `GET /market-data` · `GET /signals` · `GET /ai` · `GET /system`

Every mutation validates → authorizes → runs in a transaction → writes an audit row in that same transaction.

## 6. Frontend routes added

`/admin` (shell+guard), `/admin/` (Overview), `/admin/users`, `/admin/users/$userId`, `/admin/roles`, `/admin/subscriptions`, `/admin/audit`, `/admin/flags`, `/admin/market-data`, `/admin/signals`, `/admin/ai`, `/admin/system`.

## 7. Key files

**Backend created:** `database/migrations/20260727120000_admin_dashboard.sql`; `scripts/apply_admin_migrations.py`, `scripts/grant_admin.py`; `src/app/api/admin/*` (10 modules); `src/app/services/admin/*` (authz, audit, users, roles, flags, overview, monitoring, bootstrap); `src/app/repositories/admin/*` (roles, users, audit, flags, metrics, monitoring); `src/app/schemas/admin.py`; `tests/admin/*`.
**Backend modified:** `main.py` (router + lifespan bootstrap), `middleware/auth.py` (`/api/admin` + request-id), `services/auth.py` (suspension), `services/users.py` + `repositories/user_repo.py` (account_status), `config.py` (`ADMIN_BOOTSTRAP_EMAILS`).
**Frontend created:** `src/routes/admin*.tsx` (12); `src/features/admin/**` (shell, guard, pages, data, ui, permissions, test).
**Frontend modified:** `src/lib/psx/client.ts` (`userPut`), `src/components/layout/Sidebar.tsx` (conditional Admin link), `src/routes/__root.tsx` (admin bare-render branch).

## 8. Security approach

Server-side authorization on every action; RLS deny-all on admin tables; append-only audit; no service-role key or API keys in the browser; suspended users blocked at auth; escalation and last-super-admin guards; typed/validated flags (no free-form KV); confirmations on destructive actions; PII/financial summaries only (no secrets, no raw user conversations).

## 9. First administrator (bootstrap) — see `backend/docs/admin-dashboard.md`

1. Set `ADMIN_BOOTSTRAP_EMAILS=you@example.com` in `backend/.env` (the user must already exist in Supabase auth).
2. Start the backend. If no super_admin exists, matching users are granted `super_admin` and a `system:bootstrap` audit row is written. Idempotent + self-disabling.
3. Later grants: `python -m scripts.grant_admin grant <email> [role]`. Never edit local storage or code to gain access.

## 10. Verification results

- **Backend admin tests** (`tests/admin/`): **19 passed** — non/scoped/super authz, permission scoping, escalation blocked, last-super-admin protection, flag typing, suspension enforcement, bootstrap parsing. DB-free (monkeypatched).
- **Frontend tests**: **55 passed** (full suite; includes admin permission + PKT-format tests).
- **Web typecheck** (`tsc --noEmit`): **OK.**
- **Web lint** (admin + edited files): **0 errors, 0 warnings.**
- **Regression**: no existing test references the changed auth helpers; sampled backend suites (`test_ai_api`, `test_ai_config`) pass.
- **Not run here:** the migration against the live Supabase DB (operator action — see §4) and a live end-to-end sign-in (needs env/DB).

## 11. Implementation checklist

- [x] **Completed** — Migrations, RLS, seeds, apply script, ledger, PENDING doc
- [x] **Completed** — Backend authz (roles/permissions resolver, `require_admin`, `require_permission`, demo/non-admin deny)
- [x] **Completed** — Append-only audit (service + repo + DB trigger)
- [x] **Completed** — First-admin bootstrap (env allowlist, idempotent) + `grant_admin.py`
- [x] **Completed** — Suspension enforcement at the identity boundary
- [x] **Completed** — Admin API (me, overview, users, roles, subscriptions, audit, flags) + thin routes/services/repos/schemas
- [x] **Completed** — Read-only monitoring (market-data, signals, AI, system)
- [x] **Completed** — Frontend shell, guard, conditional nav
- [x] **Completed** — Pages: Overview, Users, User detail, Roles, Subscriptions, Audit, Flags, monitoring
- [x] **Completed** — Escalation + last-super-admin guards
- [x] **Completed** — Tests (backend authz/guards, frontend permission/format), typecheck, lint
- [x] **Completed** — Docs (this file, `backend/docs/admin-dashboard.md`, CLAUDE.md)
- [ ] **Deferred** — User impersonation (extension point; audited, super-admin-only when built)
- [ ] **Deferred** — Support/feedback case tooling
- [ ] **Deferred** — LearnHub/content CRUD (content_admin role seeded as the hook)
- [ ] **Deferred** — Notification broadcast/campaigns
- [ ] **Deferred** — Payment-provider integration for subscriptions
- [ ] **Deferred** — Editable enum/int flags UI (bool flags are toggle-editable now; typed values validated server-side)
- [x] **Completed** — Migration **applied to the live Supabase DB** (2026-07-27). Verified: 7 roles / 20 permissions / 60 mappings / 6 flags seeded; RLS enabled + service-role-only on all 7 admin tables; **no anon/authenticated grants** (browsers cannot read/self-grant); append-only audit trigger present; `profiles.account_status` added; ledger recorded.
- [x] **Completed** — First `super_admin` granted to `usmankhalidj15@gmail.com` (2026-07-27) and audited. Verified in production: RLS blocks anon/authenticated; audit log is append-only (UPDATE/DELETE both blocked by the trigger — tested live). Remaining: a live browser sign-in as this user to see `/admin` (needs the app running).

## 12. Known limitations

- Flag UI edits booleans in place; enum/int/string flags are shown read-only in the UI (backend PUT + validation already support them).
- Market-data "refresh" permission (`market_data.refresh`) is seeded but no destructive manual-trigger button is exposed yet (monitoring is read-only by design).
- User "delete" permission is seeded but no delete workflow is exposed in this pass (soft-delete recommended when built).
- Monitoring reads assume the operational tables exist; each block degrades to an honest "unavailable" state if a query fails.

## 13. Recommended next steps

1. Apply the migration to production and complete the bootstrap; verify the live guard (admin sees `/admin`, normal user is redirected + `GET /api/admin/me` 403).
2. Add the enum/int/string flag editors and a guarded market-data refresh action.
3. Build support-case tooling and content CRUD on the seeded roles.
4. Add impersonation (read-only, super-admin-only, fully audited) once the RBAC/audit foundation has bedded in.
