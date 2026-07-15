-- Workstream E: add listed_in column to psx_profile
-- Even though we now use a hardcoded Shariah list for derivation,
-- having the raw DPS field available enables future dynamic updates.
-- Spec: (internal workstream plan)

ALTER TABLE psx_profile ADD COLUMN IF NOT EXISTS listed_in text;

-- Column-level GRANT removed: the table-level GRANT in 20260706120000 already
-- covers SELECT on all columns. Column-level grants would require a prior
-- REVOKE of the table-level grant to be meaningful.
