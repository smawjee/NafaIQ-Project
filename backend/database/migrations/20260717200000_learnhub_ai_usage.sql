-- Per-user daily counter for LearnHub's LLM-backed features (quiz
-- explanations, lesson summaries), served by /api/learn/ai/*.
--
-- Why this is SEPARATE from the tutor's `ai_usage` table — the whole point of
-- this migration:
--   * LearnHub AI must not CONSUME the user's tutor allowance: asking for a
--     quiz explanation while revising must never be the reason the chatbot
--     stops answering later that day.
--   * LearnHub AI must not be LIMITED BY it either: a user who spent the day
--     chatting must still get explanations while working through a lesson.
--   * The tutor's quota table and code are off-limits by project decision
--     (2026-07-16, user-confirmed): the tutor is "not modified in any way".
--     Sharing a counter would couple the two features' limits forever, so the
--     boundary is a separate table, not a shared one with a `feature` column.
-- Two tables, two budgets, no shared state. tests/test_tutor_isolation.py and
-- tests/test_learnhub_generation.py both enforce this.
--
-- Why (user_id, day) as the PK: the counter is read-modify-written on every
-- request, and the API increments it with a single guarded
-- INSERT ... ON CONFLICT DO UPDATE ... WHERE count < :limit. The PK IS the
-- conflict target that makes that statement atomic — a read-then-write would
-- let two concurrent requests both pass the limit.
--
-- `day` is the PSX/Asia-Karachi calendar day (repositories/learnhub_usage.py
-- casts now() in that zone, matching the market timezone the scheduler pins),
-- so a learner's allowance rolls over at their local midnight, not UTC's.
--
-- Access control — the same lesson as the sibling learnhub_rag migration:
-- Supabase's DEFAULT PRIVILEGES grant table-level privileges to
-- anon/authenticated on every new public table, so enabling RLS alone is NOT
-- enough. The anon key ships in the browser bundle, and a client that can
-- UPDATE this table can reset its own counter — revoke explicitly.
--
-- Idempotent / re-runnable: IF NOT EXISTS on the table; REVOKE-then-GRANT
-- converges to the same state on every run. No sequence here (the PK is
-- natural, not a bigserial), so there is no sequence grant to revoke.

BEGIN;

CREATE TABLE IF NOT EXISTS public.learnhub_ai_usage (
    -- No FK to auth.users: the id comes from a verified Supabase JWT, and a
    -- cross-schema FK would make this table's writes depend on auth schema
    -- grants for no integrity we don't already have.
    user_id    uuid        NOT NULL,
    day        date        NOT NULL,
    count      int         NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, day)
);

-- No secondary indexes: every access is a PK lookup on (user_id, day). A
-- retention sweep by `day` alone would scan, but this table is tiny and rows
-- are ~40 bytes; revisit only if a cleanup job ever needs it.

ALTER TABLE public.learnhub_ai_usage ENABLE ROW LEVEL SECURITY;

-- No policies on purpose: service_role bypasses RLS, and with zero policies
-- nothing else can touch a row even if a grant ever leaks back in. Users never
-- read their own counter directly — the API returns it.

-- Supabase DEFAULT PRIVILEGES grant anon/authenticated access to every new
-- public table — revoke explicitly, don't rely on RLS alone.
REVOKE ALL ON TABLE public.learnhub_ai_usage FROM anon, authenticated;

GRANT ALL ON TABLE public.learnhub_ai_usage TO service_role;

COMMENT ON TABLE public.learnhub_ai_usage IS
    'Per-user daily call counter for LearnHub AI (/api/learn/ai/*), keyed by '
    'Asia/Karachi calendar day. Deliberately separate from the AI tutor''s '
    'ai_usage table: the two features must not share or exhaust each other''s '
    'allowance. Backend-internal (service_role only).';

COMMIT;
