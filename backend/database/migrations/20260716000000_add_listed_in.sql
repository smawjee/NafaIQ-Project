-- Workstream E: add listed_in column to psx_profile
-- Even though we now use a hardcoded Shariah list for derivation,
-- having the raw DPS field available enables future dynamic updates.
-- Spec: (internal workstream plan)

ALTER TABLE psx_profile ADD COLUMN IF NOT EXISTS listed_in text;

-- Grant select to anon/authenticated for consistency
GRANT SELECT (symbol, listed_in) ON psx_profile TO anon, authenticated;
