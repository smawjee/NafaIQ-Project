-- Run ANALYZE on all public tables to refresh planner statistics.
-- Many tables showed -1 row estimates because ANALYZE was never run.
-- Spec: (internal workstream plan)

ANALYZE;
