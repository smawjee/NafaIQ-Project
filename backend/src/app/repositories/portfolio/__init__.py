"""Portfolio data-access package: portfolios, holdings, priced/aggregation
reads, watchlist, and stock transactions. All portfolio-domain SQL lives here;
every function takes an executor so the service owns the transaction boundary.

Re-exports the public functions so callers keep using
`from app.repositories import portfolio as repo` and call `repo.<fn>`.
"""
from app.repositories.portfolio.holdings import (  # noqa: F401
    count_holdings,
    delete_holding,
    delete_holding_by_id,
    get_holding_by_symbol,
    insert_holding,
    is_holding_owned,
    list_holdings,
    set_holding_shares,
    update_holding_fields,
    update_holding_position,
    upsert_holding_add,
)
from app.repositories.portfolio.portfolios import (  # noqa: F401
    count_user_portfolios,
    first_portfolio_id,
    get_portfolio_name,
    insert_portfolio,
    is_portfolio_owned,
    list_portfolios,
)
from app.repositories.portfolio.trades import (  # noqa: F401
    insert_finance_reflection,
    insert_stock_transaction,
    list_stock_transactions,
)
from app.repositories.portfolio.valuation import (  # noqa: F401
    fetch_holding_symbols,
    fetch_networth_holdings,
    fetch_portfolio_history_rows,
    fetch_portfolio_live_value,
    fetch_portfolio_value_holdings,
    fetch_priced_holdings,
    fetch_symbol_ohlcv,
)
from app.repositories.portfolio.watchlist import (  # noqa: F401
    fetch_watchlist_enriched,
)
