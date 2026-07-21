"""Portfolio service package: holdings & portfolio CRUD, valuation/analytics,
watchlist enrichment, and trades. All DB access is delegated to
app.repositories.portfolio; these modules hold no SQL.

Re-exports the public functions so callers can keep using
`from app.services import portfolio as portfolio_service` and call
`portfolio_service.<fn>`.
"""
from app.services.portfolio.holdings import (  # noqa: F401
    add_holding,
    create_portfolio,
    delete_holding,
    list_holdings,
    list_holdings_owned,
    list_portfolios,
    resolve_owned_portfolio,
    sell_holding,
    update_holding,
)
from app.services.portfolio.networth import (  # noqa: F401
    allocation,
    history,
    networth,
    performance_vs_kse100,
    portfolio_history,
    portfolio_value,
    value_for_portfolio,
)
from app.services.portfolio.trades import (  # noqa: F401
    create_stock_transaction,
    detect_holding_drift,
    list_stock_transactions,
    rebuild_holdings_from_transactions,
    record_trade_atomic,
)
from app.services.portfolio.watchlist import (  # noqa: F401
    add_to_watchlist,
    enriched_watchlist,
    remove_from_watchlist,
)
