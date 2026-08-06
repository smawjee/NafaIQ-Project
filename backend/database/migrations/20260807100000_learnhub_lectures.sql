-- ---------------------------------------------------------------------------
-- LearnHub lectures: admin-managed official lessons.
--
-- Until now the official Learn Hub catalogue lived only in the frontend
-- (frontend/packages/web/src/lib/learn/data.ts), so adding or retiring a
-- lecture meant a code change and a redeploy. This table makes the catalogue
-- editable from the admin console at runtime.
--
-- The static catalogue is NOT migrated here — it keeps working and is merged
-- with these rows at read time. That way this migration cannot break the
-- existing Learn Hub, and a row added here is purely additive.
--
-- `status` is what hides a lecture from learners. Deleting a row is also
-- supported (the admin console offers both), but archiving is preferred
-- because it is reversible and keeps the audit trail meaningful.
-- ---------------------------------------------------------------------------

BEGIN;

CREATE TABLE IF NOT EXISTS public.learnhub_lectures (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Stable, human-readable key used in URLs (/learn/lesson/$id). Unique so
    -- two lectures can never fight over the same route.
    slug          TEXT NOT NULL UNIQUE
                  CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    title         TEXT NOT NULL CHECK (length(btrim(title)) > 0),
    subtitle      TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT 'PSX Basics',
    level         TEXT NOT NULL DEFAULT 'Beginner'
                  CHECK (level IN ('Beginner', 'Intermediate', 'Advanced')),
    -- Free-text so "8 min" and "1 hr" both work; the UI only ever displays it.
    duration      TEXT NOT NULL DEFAULT '5 min',
    emoji         TEXT NOT NULL DEFAULT '📘',
    accent        TEXT NOT NULL DEFAULT '#00d4aa'
                  CHECK (accent ~ '^#[0-9a-fA-F]{6}$'),
    type          TEXT NOT NULL DEFAULT 'article'
                  CHECK (type IN ('article', 'video')),
    video_url     TEXT,
    -- Lesson body: [{ id, heading, blocks: [...] }] matching LessonSection in
    -- the frontend, so a DB lecture renders through the same components.
    sections      JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- [{ q, options, correct, explanation }] matching QuizQuestion.
    quiz          JSONB NOT NULL DEFAULT '[]'::jsonb,
    status        TEXT NOT NULL DEFAULT 'published'
                  CHECK (status IN ('draft', 'published', 'archived')),
    -- Ascending; ties fall back to created_at so ordering is always total.
    sort_order    INTEGER NOT NULL DEFAULT 100,
    created_by    UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    updated_by    UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Learners only ever read published rows in catalogue order.
CREATE INDEX IF NOT EXISTS learnhub_lectures_published_idx
    ON public.learnhub_lectures (sort_order, created_at)
    WHERE status = 'published';

-- Same posture as every other admin-managed table: service_role only, so a
-- browser holding an anon/authenticated key cannot read drafts or write rows.
ALTER TABLE public.learnhub_lectures ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "learnhub_lectures_service_all" ON public.learnhub_lectures;
CREATE POLICY "learnhub_lectures_service_all" ON public.learnhub_lectures
    FOR ALL TO service_role USING (true) WITH CHECK (true);
REVOKE ALL ON public.learnhub_lectures FROM anon, authenticated;
GRANT ALL ON public.learnhub_lectures TO service_role;

-- ---------------------------------------------------------------------------
-- Permissions. `content_admin` already exists as an "extension point" role
-- with only read permissions; this is the capability it was created for.
-- ---------------------------------------------------------------------------
INSERT INTO public.admin_permissions (slug, description) VALUES
    ('learn.read',  'View the LearnHub lecture catalogue.'),
    ('learn.write', 'Create, edit, archive and delete LearnHub lectures.')
ON CONFLICT (slug) DO NOTHING;

-- super_admin gets every permission; re-run the same rule the base migration
-- used so this new pair is picked up.
INSERT INTO public.admin_role_permissions (role_slug, permission_slug)
    SELECT 'super_admin', slug FROM public.admin_permissions
ON CONFLICT DO NOTHING;

-- analyst_readonly gets every *.read permission, by the same rule.
INSERT INTO public.admin_role_permissions (role_slug, permission_slug)
    SELECT 'analyst_readonly', slug FROM public.admin_permissions WHERE slug LIKE '%.read'
ON CONFLICT DO NOTHING;

INSERT INTO public.admin_role_permissions (role_slug, permission_slug) VALUES
    ('content_admin', 'learn.read'),
    ('content_admin', 'learn.write')
ON CONFLICT DO NOTHING;

COMMIT;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260807100000_learnhub_lectures.sql', now())
ON CONFLICT (filename) DO NOTHING;
