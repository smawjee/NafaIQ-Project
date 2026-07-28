-- ---------------------------------------------------------------------------
-- Admin console: alerts oversight permission, and removal of permissions that
-- advertise capabilities no endpoint implements.
--
-- Context: the original admin seed created three permissions with no route
-- behind them. They rendered as capability badges on the Roles screen and in
-- role descriptions, promising powers the API does not have:
--
--   * market_data.refresh  -> NOW IMPLEMENTED (POST /api/admin/market-data/refresh),
--                             so it stays and is left mapped to data_admin.
--   * users.delete         -> no route. Removed.
--   * subscriptions.write  -> no route; tier changes go through users.tier.write,
--                             which finance_admin already holds. Removed.
--
-- Idempotent: safe to re-run.
-- ---------------------------------------------------------------------------

-- 1. New permission for the alerts oversight screen.
INSERT INTO public.admin_permissions (slug, description) VALUES
    ('alerts.read', 'View platform-wide alert volume and delivery health.')
ON CONFLICT (slug) DO UPDATE SET description = EXCLUDED.description;

-- 2. Re-apply the standing role rules so the new permission is picked up.
--    super_admin holds every permission; analyst_readonly holds every read.
INSERT INTO public.admin_role_permissions (role_slug, permission_slug)
    SELECT 'super_admin', slug FROM public.admin_permissions
ON CONFLICT DO NOTHING;

INSERT INTO public.admin_role_permissions (role_slug, permission_slug)
    SELECT 'analyst_readonly', slug FROM public.admin_permissions WHERE slug LIKE '%.read'
ON CONFLICT DO NOTHING;

-- Alerts are an operational concern (delivery health) and a support concern
-- (is this user's alert firing?), so both those roles get the read.
INSERT INTO public.admin_role_permissions (role_slug, permission_slug) VALUES
    ('data_admin',    'alerts.read'),
    ('support_admin', 'alerts.read')
ON CONFLICT DO NOTHING;

-- 3. Drop the two unimplemented permissions. Mappings must go first — the
--    role_permissions FK references admin_permissions(slug).
DELETE FROM public.admin_role_permissions
    WHERE permission_slug IN ('users.delete', 'subscriptions.write');

DELETE FROM public.admin_permissions
    WHERE slug IN ('users.delete', 'subscriptions.write');

-- 4. finance_admin's description referenced entitlement management it never had.
UPDATE public.admin_roles
   SET description = 'Manage subscription tiers on user accounts.'
 WHERE slug = 'finance_admin';

-- ---------------------------------------------------------------------------
-- Migration ledger
-- ---------------------------------------------------------------------------
INSERT INTO public._applied_migrations (filename) VALUES
    ('20260728090000_admin_alerts_and_dead_permissions.sql')
ON CONFLICT (filename) DO NOTHING;
