"""Market data service package: quote/reference reads, history, indicators,
screener/backtest, and the TradingView heatmap. Live external sources are
orchestrated here; the only own-DB queries (sector averages, history coverage,
screener metrics) are delegated to app.repositories.market.

Re-exports the public functions so callers keep using
`from app.services import market as market_service` and call `market_service.<fn>`.
"""
from app.services.market._base import get_cache  # noqa: F401
from app.services.market.heatmap import heatmap, sector_averages  # noqa: F401
from app.services.market.history import history, history_coverage  # noqa: F401
from app.services.market.indicators import indicators  # noqa: F401
from app.services.market.quotes import (  # noqa: F401
    announcements,
    dividends,
    fundamentals,
    index_cards,
    index_eod,
    market_snapshot,
    profile,
    quote,
    sectors,
    symbols,
)
from app.services.market.screener import (  # noqa: F401
    run_backtest_top,
    run_screener,
    screener_metrics,
)
