-- LearnHub Studio private media storage.
--
-- The API and worker always use the service role. Browser/mobile clients never
-- access this bucket directly; playback is exposed through short-lived signed
-- URLs issued only after the API verifies project ownership.
BEGIN;

INSERT INTO storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
VALUES (
    'learnhub-studio',
    'learnhub-studio',
    false,
    104857600,
    ARRAY['application/pdf', 'video/mp4', 'text/vtt', 'image/png']::text[]
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    public = false,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types,
    updated_at = now();

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260807110000_learnhub_studio_media_bucket.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
