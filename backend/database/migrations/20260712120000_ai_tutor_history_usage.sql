-- AI Tutor Phase 6: persisted chat history + daily usage tracking + Pro quota.
-- Spec: docs/superpowers/specs/2026-07-12-learnhub-ai-tutor-phase6.md
-- Apply via Supabase Dashboard SQL Editor.

-- ============ ai_chat_history ============
CREATE TABLE IF NOT EXISTS public.ai_chat_history (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content      TEXT NOT NULL,
    lesson_title TEXT,
    lang         TEXT CHECK (lang IN ('en', 'ur')),
    provider     TEXT,
    model        TEXT,
    tokens_in    INT,
    tokens_out   INT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_chat_history_user_created
    ON public.ai_chat_history (user_id, created_at DESC);

ALTER TABLE public.ai_chat_history ENABLE ROW LEVEL SECURITY;

-- Owner-only reads; all writes happen server-side via the service role.
DROP POLICY IF EXISTS "ai_chat_history_owner_select" ON public.ai_chat_history;
CREATE POLICY "ai_chat_history_owner_select" ON public.ai_chat_history
    FOR SELECT USING (auth.uid() = user_id);

GRANT SELECT ON public.ai_chat_history TO authenticated;
GRANT ALL ON public.ai_chat_history TO service_role;

-- ============ ai_usage ============
CREATE TABLE IF NOT EXISTS public.ai_usage (
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    usage_date    DATE NOT NULL,
    message_count INT NOT NULL DEFAULT 0,
    tokens_in     INT NOT NULL DEFAULT 0,
    tokens_out    INT NOT NULL DEFAULT 0,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, usage_date)
);

ALTER TABLE public.ai_usage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ai_usage_owner_select" ON public.ai_usage;
CREATE POLICY "ai_usage_owner_select" ON public.ai_usage
    FOR SELECT USING (auth.uid() = user_id);

GRANT SELECT ON public.ai_usage TO authenticated;
GRANT ALL ON public.ai_usage TO service_role;

-- ============ plan quota ============
-- Free already 10, Premium already NULL (unlimited). Pro: NULL -> 100/day.
UPDATE public.plan_features SET ai_tutor_daily_limit = 100 WHERE plan = 'Pro';
