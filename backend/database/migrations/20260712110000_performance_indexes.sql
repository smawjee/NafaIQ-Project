-- 20260712110000_performance_indexes.sql
-- Add performance indexes identified by codebase audit.
-- All use IF NOT EXISTS so they are safe to re-run.

-- Critical: psx_ohlcv(symbol, date DESC)
-- Used by DISTINCT ON (symbol) ORDER BY symbol, date DESC in valuation.py
-- (fetch_priced_holdings, fetch_networth_holdings) and by
-- LEFT JOIN LATERAL (SELECT ... WHERE symbol = ? ORDER BY date DESC LIMIT 1)
-- in fetch_portfolio_value_holdings and fetch_portfolio_live_value.
CREATE INDEX IF NOT EXISTS idx_psx_ohlcv_symbol_date_desc
  ON psx_ohlcv (symbol, date DESC);

-- psx_holdings(portfolio_id, symbol)
-- Speeds up JOIN on portfolio_id and ORDER BY symbol in portfolio queries.
CREATE INDEX IF NOT EXISTS idx_psx_holdings_portfolio_id_symbol
  ON psx_holdings (portfolio_id, symbol);

-- psx_market_snapshot(symbol)
-- Speeds up LEFT JOIN on symbol in portfolio valuation and quote lookups.
CREATE INDEX IF NOT EXISTS idx_psx_market_snapshot_symbol
  ON psx_market_snapshot (symbol);

-- stock_transactions(user_id, executed_at DESC)
-- Speeds up today_buys CTE in fetch_networth_holdings (valuation.py).
CREATE INDEX IF NOT EXISTS idx_stock_transactions_user_id_executed_at
  ON stock_transactions (user_id, executed_at DESC);

-- user_transactions(user_id, transaction_date DESC)
-- Speeds up budget spent calculation and monthly summaries.
CREATE INDEX IF NOT EXISTS idx_user_transactions_user_id_date
  ON user_transactions (user_id, transaction_date DESC);

-- psx_signals(symbol)
-- Speeds up signal cache lookups in signal_engine.py.
CREATE INDEX IF NOT EXISTS idx_psx_signals_symbol
  ON psx_signals (symbol);

-- psx_announcements(refreshed_at)
-- Speeds up staleness check in cache.py get_announcements().
CREATE INDEX IF NOT EXISTS idx_psx_announcements_refreshed_at
  ON psx_announcements (refreshed_at);

-- Lowercase existing categories in user_budgets to match the new
-- case-sensitive join with user_transactions (categories are now
-- normalized to lowercase on insert/update).
UPDATE user_budgets SET category = LOWER(category) WHERE category IS DISTINCT FROM LOWER(category);
