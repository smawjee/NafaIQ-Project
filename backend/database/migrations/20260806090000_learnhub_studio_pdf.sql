-- LearnHub Studio private PDF projects.
-- Uploaded documents remain private objects; only the owning user's project
-- can reference them and PDF-derived artifacts are never shared by cache.
BEGIN;

ALTER TABLE public.learnhub_studio_projects
    ADD COLUMN IF NOT EXISTS source_kind text NOT NULL DEFAULT 'topic'
        CHECK (source_kind IN ('topic', 'pdf'));

ALTER TABLE public.learnhub_studio_artifacts
    ADD COLUMN IF NOT EXISTS owner_user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.learnhub_studio_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL UNIQUE
        REFERENCES public.learnhub_studio_projects(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    original_name text NOT NULL,
    object_path text NOT NULL UNIQUE,
    mime_type text NOT NULL DEFAULT 'application/pdf',
    size_bytes integer NOT NULL CHECK (size_bytes > 0),
    content_hash text NOT NULL,
    page_count integer CHECK (page_count > 0),
    extracted_sources jsonb NOT NULL DEFAULT '[]'::jsonb,
    extraction_status text NOT NULL DEFAULT 'uploaded'
        CHECK (extraction_status IN ('uploaded', 'extracting', 'ready', 'failed')),
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learnhub_studio_documents_user
    ON public.learnhub_studio_documents(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_learnhub_studio_artifacts_owner
    ON public.learnhub_studio_artifacts(owner_user_id)
    WHERE owner_user_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.learnhub_studio_cleanup_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    object_paths jsonb NOT NULL,
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_learnhub_studio_cleanup_claim
    ON public.learnhub_studio_cleanup_jobs(status, available_at, created_at);

ALTER TABLE public.learnhub_studio_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learnhub_studio_cleanup_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.learnhub_studio_documents FROM anon, authenticated;
REVOKE ALL ON TABLE public.learnhub_studio_cleanup_jobs FROM anon, authenticated;
GRANT ALL ON TABLE public.learnhub_studio_documents TO service_role;
GRANT ALL ON TABLE public.learnhub_studio_cleanup_jobs TO service_role;

COMMIT;
