-- Performance indexes for mutual funds queries
-- Spec: (internal workstream plan)

CREATE INDEX IF NOT EXISTS idx_psx_mutual_funds_category ON psx_mutual_funds(category);
CREATE INDEX IF NOT EXISTS idx_psx_fund_nav_history_fund_code ON psx_fund_nav_history(fund_code);
CREATE INDEX IF NOT EXISTS idx_psx_fund_nav_history_date ON psx_fund_nav_history(date DESC);
