"""Market data-access package: own-DB PSX queries only (symbol existence,
sector averages, market caps, recent closes, history coverage). Live external
sources are orchestrated in app.services.market.

Re-exports the public functions so callers keep using
`from app.repositories import market as repo` and call `repo.<fn>`.
"""
from app.repositories.market.metrics import (  # noqa: F401
    history_coverage,
    market_caps,
    recent_closes,
    sector_averages,
)
from app.repositories.market.reference import symbol_is_known  # noqa: F401
