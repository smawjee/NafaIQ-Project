-- Per-user daily counter for the NafaIQ Assistant (/api/assistant/*), the
-- voice-and-text agent behind the "Ask NafaIQ AI" sidebar CTA.
--
-- Why a THIRD counter table, alongside ai_usage (tutor) and learnhub_ai_usage:
-- the same isolation rule that produced the second one applies again here.
--   * The assistant must not CONSUME the tutor's allowance: adding a
--     transaction by voice must never be the reason the LearnHub chatbot stops
--     answering later that day.
--   * The assistant must not be LIMITED BY it either: a user who spent the day
--     revising lessons must still be able to log an expense.
--   * The tutor's quota table and code remain off-limits by project decision
--     (2026-07-16, user-confirmed, reaffirmed 2026-07-22 when this feature was
--     scoped: "don't touch RAG"). Sharing a counter would couple the features'
--     limits forever, so the boundary is a separate table — not a shared one
--     with a `feature` column.
-- Three tables, three budgets, no shared state.
--
-- Structure is deliberately identical to learnhub_ai_usage so the atomic
-- check-and-increment idiom in repositories/assistant_usage.py is the same
-- statement shape: (user_id, day) PK IS the conflict target that makes
-- INSERT ... ON CONFLICT DO UPDATE ... WHERE count < :limit atomic. A
-- read-then-write would let two concurrent requests both pass the limit.
--
-- `day` is the PSX/Asia-Karachi calendar day, matching learnhub_ai_usage and
-- the market timezone the scheduler pins, so an allowance rolls over at the
-- user's local midnight rather than at 5am local (UTC midnight).
--
-- Access control: Supabase DEFAULT PRIVILEGES grant anon/authenticated on every
-- new public table, so enabling RLS alone is NOT enough. The anon key ships in
-- the browser bundle, and a client that can UPDATE this table can reset its own
-- counter — revoke explicitly.
--
-- Idempotent / re-runnable: IF NOT EXISTS on the table; REVOKE-then-GRANT
-- converges to the same state on every run. No sequence (the PK is natural).

BEGIN;

CREATE TABLE IF NOT EXISTS public.assistant_usage (
    -- No FK to auth.users: the id comes from a verified Supabase JWT, and a
    -- cross-schema FK would make this table's writes depend on auth schema
    -- grants for no integrity we don't already have.
    user_id    uuid        NOT NULL,
    day        date        NOT NULL,
    count      int         NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, day)
);

ALTER TABLE public.assistant_usage ENABLE ROW LEVEL SECURITY;

-- No policies on purpose: service_role bypasses RLS, and with zero policies
-- nothing else can touch a row even if a grant ever leaks back in. Users never
-- read their own counter directly — the API returns it.

REVOKE ALL ON TABLE public.assistant_usage FROM anon, authenticated;

GRANT ALL ON TABLE public.assistant_usage TO service_role;

COMMENT ON TABLE public.assistant_usage IS
    'Per-user daily turn counter for the NafaIQ Assistant (/api/assistant/*), '
    'keyed by Asia/Karachi calendar day. Deliberately separate from both the AI '
    'tutor''s ai_usage and learnhub_ai_usage: the three features must not share '
    'or exhaust each other''s allowance. Backend-internal (service_role only).';

COMMIT;
