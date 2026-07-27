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
doesn't match the flag's declared type is rejected. Starter flags:
`registration_enabled`, `maintenance_mode`, `ai_features_enabled`,
`assistant_enabled`, `reports_enabled`, `signals_enabled`.

## Audit log

`/admin/audit` (permission `audit.read`) is filterable by action and status and
paginated. Entries are immutable — the table blocks UPDATE/DELETE at the database
level, so the trail cannot be rewritten, even by the backend.

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
