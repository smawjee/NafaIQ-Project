-- Add TradingView logo identifier to psx_profile for stock logos (2026-07-09).
-- Populated from the TradingView scanner "logoid" column; the frontend builds
-- the image URL as https://s3-symbol-logo.tradingview.com/{logoid}.svg
ALTER TABLE public.psx_profile ADD COLUMN IF NOT EXISTS logoid text;
