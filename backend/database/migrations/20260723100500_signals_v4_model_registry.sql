-- Signals V4 model registry. RED artifacts are retained for audit but are not
-- loadable by a scoring job.

BEGIN;

CREATE TABLE IF NOT EXISTS public.psx_signal_model_registry (
    model_version        TEXT PRIMARY KEY,
    horizon_sessions     INT NOT NULL,
    feature_version      TEXT NOT NULL,
    artifact_uri         TEXT NOT NULL,
    artifact_sha256      TEXT NOT NULL,
    status               TEXT NOT NULL,
    promotion_manifest   JSONB NOT NULL DEFAULT '{}'::jsonb,
    shadow_started_at    TIMESTAMPTZ,
    shadow_matured_count INT NOT NULL DEFAULT 0,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT psx_signal_model_registry_status_check
        CHECK (status IN ('RED', 'SHADOW', 'PROMOTED', 'RETIRED')),
    CONSTRAINT psx_signal_model_registry_horizon_check
        CHECK (horizon_sessions = 20)
);

ALTER TABLE public.psx_signal_model_registry ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.psx_signal_model_registry FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.psx_signal_model_registry TO service_role;

INSERT INTO public._applied_migrations(filename, applied_at)
VALUES ('20260723100500_signals_v4_model_registry.sql', now())
ON CONFLICT (filename) DO NOTHING;

COMMIT;
