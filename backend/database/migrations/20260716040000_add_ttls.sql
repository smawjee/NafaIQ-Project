-- Add TTL support for high-volume tables.
-- psx_unusual_activity: keep 7 days
-- psx_news: keep 30 days
-- Spec: (internal workstream plan)

-- Add an index on ts for efficient cleanup queries
CREATE INDEX IF NOT EXISTS idx_psx_unusual_activity_ts ON psx_unusual_activity(ts DESC);
CREATE INDEX IF NOT EXISTS idx_psx_news_published_at ON psx_news(published_at DESC);

-- TTL cleanup is handled at the application layer (see volume_spikes.py).
