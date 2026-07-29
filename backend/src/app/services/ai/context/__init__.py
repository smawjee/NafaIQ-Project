"""Context assemblers — pull the exact rows each surface needs into a plain
JSON-serializable bundle. Each build_*_context applies cheap data-sanity guards
and folds in the deterministic confidence metrics (with None sentinels for
sparse data). The engine injects the bundle; verify.py resolves citations against it.

Key points:
- Every citable value sits at a stable dot-path (e.g. networth.total_market_value).
- conn_or_session is accepted for interface stability but unused — the data
  services manage their own DB connections.
- The EvidenceRetriever handles all unstructured text (today returns []);
  numerics never go through it.
- Pure/deterministic given fixed service outputs (tests mock the services).

Split into one module per surface (market/stock/portfolio/finance/dashboard) over
a shared helper module. The submodule service bindings are re-exported here so
`context.<service>` stays the monkeypatch point tests rely on.
"""
from ._shared import (
    finance_bills,
    finance_budgets,
    finance_goals,
    finance_summary,
    market_heatmap,
    market_history,
    market_quotes,
    portfolio_svc,
    portfolio_trades,
    sector_map_mod,
)
from .dashboard import build_dashboard_rec_context
from .finance import build_finance_context
from .market import build_market_brief_context
from .portfolio import build_portfolio_context
from .stock import build_stock_analysis_context

__all__ = [
    "build_market_brief_context",
    "build_stock_analysis_context",
    "build_portfolio_context",
    "build_finance_context",
    "build_dashboard_rec_context",
    "finance_bills",
    "finance_budgets",
    "finance_goals",
    "finance_summary",
    "market_heatmap",
    "market_history",
    "market_quotes",
    "portfolio_svc",
    "portfolio_trades",
    "sector_map_mod",
]
