-- Onboarding plan selection (2026-07-09).
-- After signup/login, users who have not yet chosen a plan are routed to the
-- /plans page; choosing one calls POST /api/profile/plan (backend service
-- connection - the prevent_profile_plan_self_update trigger still blocks
-- direct client-side plan tampering) which stamps plan_selected_at.
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS plan_selected_at timestamptz;
