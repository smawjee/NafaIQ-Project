-- Apply TV_SECTOR_MAP: remap TradingView sector taxonomy to DPS taxonomy.
-- This one-shot UPDATE replaces TV-style sectors (e.g. "Finance") with
-- their DPS equivalents (e.g. "Commercial Banks").
-- Spec: (internal workstream plan)

-- Source: backend/src/app/jobs/scheduler.py TV_SECTOR_MAP
UPDATE psx_profile SET sector = map.dps_sector
FROM (VALUES
    ('Finance', 'Commercial Banks'),
    ('Process Industries', 'Textile'),
    ('Consumer Non-Durables', 'Food & Personal Care Products'),
    ('Distribution Services', 'Distribution & Wholesale'),
    ('Technology Services', 'Technology & Communication'),
    ('Consumer Services', 'Cable & Other Services'),
    ('Producer Manufacturing', 'Engineering'),
    ('Industrial Services', 'Transport & Logistics'),
    ('Communications', 'Technology & Communication'),
    ('Electronic Technology', 'Technology & Communication'),
    ('Consumer Durables', 'Miscellaneous'),
    ('Non-Energy Minerals', 'Miscellaneous'),
    ('Energy Minerals', 'Oil & Gas'),
    ('Retail Trade', 'Miscellaneous'),
    ('Health Technology', 'Pharmaceuticals'),
    ('Utilities', 'Power Generation & Distribution'),
    ('Commercial Services', 'Miscellaneous'),
    ('Miscellaneous', 'Miscellaneous')
) AS map(tv_sector, dps_sector)
WHERE psx_profile.sector = map.tv_sector;

-- Also map the TradingView index categories
UPDATE psx_profile SET sector = map.dps_sector
FROM (VALUES
    ('Finance', 'Commercial Banks'),
    ('Process Industries', 'Textile'),
    ('Consumer Non-Durables', 'Food & Personal Care Products')
) AS map(tv_sector, dps_sector)
WHERE psx_profile.sector = map.tv_sector;
