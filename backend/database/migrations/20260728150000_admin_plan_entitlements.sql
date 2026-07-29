-- ---------------------------------------------------------------------------
-- Admin console: plan-entitlement editing + user anonymisation.
--
-- 1. RESTORES `subscriptions.write`.
--    20260728090000 removed it as a permission with no endpoint behind it. That
--    was the wrong conclusion: `plan_features` is live configuration read on
--    every request by repositories/user_repo.py:get_plan_features, and it
--    enforces real quotas (watchlist caps, AI tutor limits, per-plan feature
--    flags). The capability was real; only the route was missing. It now exists
--    (PUT /api/admin/plans/{plan}), so the permission comes back.
--
-- 2. Adds `users.anonymise` for GDPR-style erasure that scrubs PII while keeping
--    portfolio/finance records and the audit trail intact. Granted to
--    super_admin ONLY — it is irreversible, so it deliberately does not go to
--    support_admin with the rest of the user-management permissions.
--
-- Idempotent: safe to re-run.
-- ---------------------------------------------------------------------------

INSERT INTO public.admin_permissions (slug, description) VALUES
    ('subscriptions.write', 'Edit plan entitlements and quotas (plan_features).'),
    ('users.anonymise',     'Irreversibly scrub a user''s personal data, keeping their records.')
ON CONFLICT (slug) DO UPDATE SET description = EXCLUDED.description;

-- Standing rules: super_admin holds every permission; analyst_readonly holds
-- every read. Re-applied so the new slugs are picked up.
INSERT INTO public.admin_role_permissions (role_slug, permission_slug)
    SELECT 'super_admin', slug FROM public.admin_permissions
ON CONFLICT DO NOTHING;

INSERT INTO public.admin_role_permissions (role_slug, permission_slug)
    SELECT 'analyst_readonly', slug FROM public.admin_permissions WHERE slug LIKE '%.read'
ON CONFLICT DO NOTHING;

-- finance_admin owns commercial configuration, so it regains entitlement writes.
-- users.anonymise is intentionally NOT granted to any role other than super_admin.
INSERT INTO public.admin_role_permissions (role_slug, permission_slug) VALUES
    ('finance_admin', 'subscriptions.write')
ON CONFLICT DO NOTHING;

UPDATE public.admin_roles
   SET description = 'Manage subscription tiers and plan entitlements.'
 WHERE slug = 'finance_admin';

-- ---------------------------------------------------------------------------
-- Migration ledger
-- ---------------------------------------------------------------------------
INSERT INTO public._applied_migrations (filename) VALUES
    ('20260728150000_admin_plan_entitlements.sql')
ON CONFLICT (filename) DO NOTHING;
