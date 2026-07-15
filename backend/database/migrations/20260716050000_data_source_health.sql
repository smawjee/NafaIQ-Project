-- Per-source health observability table.
-- Each scraper/job writes its status here so /api/health can report
-- the health of every data source, not just psx_market_snapshot.
-- Spec: (internal workstream plan)

CREATE TABLE IF NOT EXISTS psx_data_source_health (
    source text PRIMARY KEY,
    last_success timestamptz,
    last_error timestamptz,
    last_error_message text,
    rows_updated int DEFAULT 0,
    refreshed_at timestamptz DEFAULT now()
);

ALTER TABLE psx_data_source_health ENABLE ROW LEVEL SECURITY;

-- Idempotent policy creation: drop first, then create
DROP POLICY IF EXISTS "psx_data_source_health_select" ON psx_data_source_health;
CREATE POLICY "psx_data_source_health_select"
    ON psx_data_source_health FOR SELECT
    USING (true);

GRANT SELECT ON psx_data_source_health TO anon, authenticated;
GRANT ALL ON psx_data_source_health TO service_role;
