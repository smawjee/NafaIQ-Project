-- ============================================================================
-- Admin Dashboard: RBAC, audit log, platform flags, account status
--
-- Adds a real role/permission model for platform administration, an append-only
-- audit trail, typed platform feature flags, and per-account status (for
-- suspension). NON-DESTRUCTIVE: only CREATE ... IF NOT EXISTS and ALTER TABLE
-- ADD COLUMN IF NOT EXISTS. No existing table is dropped or rewritten.
--
-- SECURITY MODEL
--   * Every admin table has RLS ENABLED with NO anon/authenticated policy
--     (deny-all for browsers going through PostgREST) and a service_role
--     FOR ALL policy. The backend reaches these tables via the SQLAlchemy
--     transaction-pooler connection (privileged role), never the browser.
--     This is what prevents a user from self-granting admin: the client simply
--     cannot see or write these rows.
--   * admin_audit_log is append-only, enforced by a BEFORE UPDATE/DELETE trigger
--     that raises — so even the backend cannot rewrite history.
--   * profiles.account_status is added but NOT exposed to client writes; the
--     existing profiles RLS already blocks authenticated users from updating
--     restricted columns, and suspension is only ever set through /api/admin.
--
-- Re-runnable: guarded with IF NOT EXISTS / ON CONFLICT DO NOTHING /
-- DROP POLICY IF EXISTS, all inside one transaction.
-- ============================================================================

BEGIN;

-- Transaction-local settings (safe on the transaction pooler). The only
-- contended object here is public.profiles, which the live app reads on every
-- authenticated request; ADD COLUMN needs a brief ACCESS EXCLUSIVE lock, so we
-- bound the wait (fail fast → the apply script retries) rather than blocking up
-- to the server statement_timeout. No per-statement timeout otherwise.
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = 0;

-- ---------------------------------------------------------------------------
-- 1. Roles, permissions, and their mapping (static lookup, seeded below)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.admin_roles (
    slug        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS public.admin_permissions (
    slug        TEXT PRIMARY KEY,
    description TEXT
);

CREATE TABLE IF NOT EXISTS public.admin_role_permissions (
    role_slug       TEXT NOT NULL REFERENCES public.admin_roles(slug) ON DELETE CASCADE,
    permission_slug TEXT NOT NULL REFERENCES public.admin_permissions(slug) ON DELETE CASCADE,
    PRIMARY KEY (role_slug, permission_slug)
);

-- ---------------------------------------------------------------------------
-- 2. Role assignments (who is an admin). active = revoked_at IS NULL.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.admin_role_assignments (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role_slug  TEXT NOT NULL REFERENCES public.admin_roles(slug),
    granted_by UUID REFERENCES auth.users(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES auth.users(id),
    reason     TEXT
);

-- One ACTIVE assignment per (user, role); revoked rows are kept for history.
CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_role_assignment_active
    ON public.admin_role_assignments (user_id, role_slug)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_admin_role_assignments_user
    ON public.admin_role_assignments (user_id)
    WHERE revoked_at IS NULL;

-- ---------------------------------------------------------------------------
-- 3. Audit log (append-only)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.admin_audit_log (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_user_id  UUID,
    actor_email    TEXT,
    actor_roles    TEXT[] NOT NULL DEFAULT '{}',
    action         TEXT NOT NULL,
    resource_type  TEXT,
    resource_id    TEXT,
    target_user_id UUID,
    before         JSONB,
    after          JSONB,
    reason         TEXT,
    request_id     TEXT,
    ip             TEXT,
    status         TEXT NOT NULL DEFAULT 'success'
                   CHECK (status IN ('success', 'failure')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON public.admin_audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_target  ON public.admin_audit_log (target_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_actor   ON public.admin_audit_log (actor_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_action  ON public.admin_audit_log (action);

-- Append-only: block any UPDATE/DELETE, for every role (triggers fire even for
-- the table owner / service_role). The audit trail must be tamper-evident.
CREATE OR REPLACE FUNCTION public.admin_audit_log_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'admin_audit_log is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_admin_audit_log_immutable ON public.admin_audit_log;
CREATE TRIGGER trg_admin_audit_log_immutable
    BEFORE UPDATE OR DELETE ON public.admin_audit_log
    FOR EACH ROW EXECUTE FUNCTION public.admin_audit_log_immutable();

-- ---------------------------------------------------------------------------
-- 4. Admin notes on users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.admin_user_notes (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    author_id  UUID REFERENCES auth.users(id),
    note       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_user_notes_user ON public.admin_user_notes (user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 5. Platform flags (typed, validated in the service layer)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.platform_flags (
    key         TEXT PRIMARY KEY,
    type        TEXT NOT NULL CHECK (type IN ('bool', 'int', 'string', 'enum')),
    value       JSONB NOT NULL,
    allowed     JSONB,                 -- enum options, when type = 'enum'
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT,
    updated_by  UUID REFERENCES auth.users(id),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 6. Account status on profiles (for suspension / restriction)
-- ---------------------------------------------------------------------------
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS account_status TEXT NOT NULL DEFAULT 'active'
        CHECK (account_status IN ('active', 'suspended', 'restricted'));
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS status_reason TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMPTZ;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS status_changed_by UUID;

CREATE INDEX IF NOT EXISTS idx_profiles_account_status
    ON public.profiles (account_status)
    WHERE account_status <> 'active';

-- ---------------------------------------------------------------------------
-- 7. RLS + grants: deny-all for browsers, service_role only
-- ---------------------------------------------------------------------------
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'admin_roles', 'admin_permissions', 'admin_role_permissions',
        'admin_role_assignments', 'admin_audit_log', 'admin_user_notes',
        'platform_flags'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS "%s_service_all" ON public.%I', t, t);
        EXECUTE format(
            'CREATE POLICY "%s_service_all" ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)',
            t, t
        );
        -- No anon/authenticated grants: browsers via PostgREST are denied.
        EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', t);
        EXECUTE format('GRANT ALL ON public.%I TO service_role', t);
    END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- 8. Seed roles
-- ---------------------------------------------------------------------------
INSERT INTO public.admin_roles (slug, name, description) VALUES
    ('super_admin',      'Super Administrator',    'Full control over every admin capability.'),
    ('support_admin',    'Support Administrator',  'User support: inspect users, notes, suspend/reactivate.'),
    ('content_admin',    'Content Administrator',  'Manage LearnHub / educational content (extension point).'),
    ('finance_admin',    'Finance Administrator',  'Manage subscription tiers and account entitlements.'),
    ('data_admin',       'Data Operations Admin',  'Monitor market-data pipeline and signals.'),
    ('ai_admin',         'AI Operations Admin',    'Monitor AI usage and manage AI feature flags.'),
    ('analyst_readonly', 'Read-only Analyst',      'Read-only access to every admin view.')
ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;

-- ---------------------------------------------------------------------------
-- 9. Seed permissions
-- ---------------------------------------------------------------------------
INSERT INTO public.admin_permissions (slug, description) VALUES
    ('overview.read',        'View the admin overview dashboard.'),
    ('users.read',           'List and inspect users.'),
    ('users.note',           'Add administrative notes to a user.'),
    ('users.suspend',        'Suspend or reactivate a user account.'),
    ('users.tier.read',      'View a user''s subscription tier.'),
    ('users.tier.write',     'Change a user''s subscription tier.'),
    ('users.delete',         'Delete a user account (soft).'),
    ('roles.read',           'View admin role assignments.'),
    ('roles.assign',         'Assign admin roles.'),
    ('roles.revoke',         'Revoke admin roles.'),
    ('subscriptions.read',   'View subscription/tier configuration.'),
    ('subscriptions.write',  'Edit subscription/tier configuration.'),
    ('audit.read',           'View the audit log.'),
    ('flags.read',           'View platform feature flags.'),
    ('flags.write',          'Edit platform feature flags.'),
    ('market_data.read',     'View market-data pipeline health.'),
    ('market_data.refresh',  'Trigger a safe market-data refresh.'),
    ('signals.read',         'View signals monitoring.'),
    ('ai.read',              'View AI operations and usage.'),
    ('system.read',          'View system health.')
ON CONFLICT (slug) DO UPDATE SET description = EXCLUDED.description;

-- ---------------------------------------------------------------------------
-- 10. Seed role -> permission mapping
-- ---------------------------------------------------------------------------
-- super_admin: every permission.
INSERT INTO public.admin_role_permissions (role_slug, permission_slug)
    SELECT 'super_admin', slug FROM public.admin_permissions
ON CONFLICT DO NOTHING;

-- analyst_readonly: every read permission.
INSERT INTO public.admin_role_permissions (role_slug, permission_slug)
    SELECT 'analyst_readonly', slug FROM public.admin_permissions WHERE slug LIKE '%.read'
ON CONFLICT DO NOTHING;

INSERT INTO public.admin_role_permissions (role_slug, permission_slug) VALUES
    ('support_admin', 'overview.read'),
    ('support_admin', 'users.read'),
    ('support_admin', 'users.note'),
    ('support_admin', 'users.suspend'),
    ('support_admin', 'users.tier.read'),
    ('support_admin', 'audit.read'),
    ('support_admin', 'system.read'),

    ('content_admin', 'overview.read'),
    ('content_admin', 'audit.read'),
    ('content_admin', 'system.read'),

    ('finance_admin', 'overview.read'),
    ('finance_admin', 'users.read'),
    ('finance_admin', 'users.tier.read'),
    ('finance_admin', 'users.tier.write'),
    ('finance_admin', 'subscriptions.read'),
    ('finance_admin', 'subscriptions.write'),
    ('finance_admin', 'audit.read'),

    ('data_admin', 'overview.read'),
    ('data_admin', 'market_data.read'),
    ('data_admin', 'market_data.refresh'),
    ('data_admin', 'signals.read'),
    ('data_admin', 'system.read'),
    ('data_admin', 'audit.read'),

    ('ai_admin', 'overview.read'),
    ('ai_admin', 'ai.read'),
    ('ai_admin', 'flags.read'),
    ('ai_admin', 'flags.write'),
    ('ai_admin', 'audit.read'),
    ('ai_admin', 'system.read')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 11. Seed platform flags (starter set; values are jsonb of the declared type)
-- ---------------------------------------------------------------------------
INSERT INTO public.platform_flags (key, type, value, description) VALUES
    ('registration_enabled', 'bool', 'true'::jsonb,  'Allow new user sign-ups.'),
    ('maintenance_mode',     'bool', 'false'::jsonb, 'Show maintenance banner / degrade gracefully.'),
    ('ai_features_enabled',  'bool', 'true'::jsonb,  'Master switch for AI features.'),
    ('assistant_enabled',    'bool', 'true'::jsonb,  'Enable the NafaIQ Assistant.'),
    ('reports_enabled',      'bool', 'true'::jsonb,  'Enable AI report generation.'),
    ('signals_enabled',      'bool', 'true'::jsonb,  'Enable signals surfaces.')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Migration ledger
-- ---------------------------------------------------------------------------
INSERT INTO public._applied_migrations (filename) VALUES
    ('20260727120000_admin_dashboard.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
