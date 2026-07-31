"""Pure screening logic: filter + rank the market board against ScreenerParams.

Deliberately synchronous and side-effect free. `app.services.market.screener`
owns the I/O (snapshot, histories, fundamentals) and hands the assembled data
here, which keeps the filtering rules unit-testable without a database.

Filter semantics: a filter only ever *narrows* the result set. When a filter
needs a value a symbol does not have (no RSI because there is too little
history, no P/E because fundamentals were never ingested), that symbol is
dropped rather than passed through. Letting unknowns through would quietly
present unscreened stocks as if they had met the user's criteria.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from app.schemas.market import MarketSnapshotItem, ScreenerParams, SymbolInfo

# Sort keys the UI may ask for, mapped onto the assembled row.
_SORTABLE = {
    "change_pct", "change", "price", "volume",
    "pe", "pb", "roe", "div_yield", "rsi14",
}


def _indicator(entry: Any, key: str) -> Optional[float]:
    """Pull a scalar indicator out of an IndicatorResult (or a plain dict)."""
    if entry is None:
        return None
    values = getattr(entry, "indicators", None)
    if values is None and isinstance(entry, dict):
        values = entry.get("indicators", entry)
    if not isinstance(values, dict):
        return None
    raw = values.get(key)
    if isinstance(raw, dict):  # e.g. macd -> {"macd": ..., "signal": ...}
        raw = raw.get(key)
    return raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None


def _fundamental(entry: Any, key: str) -> Optional[float]:
    if not isinstance(entry, dict):
        entry = vars(entry) if entry is not None else {}
    raw = entry.get(key)
    return raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None


def screen_symbols(
    snapshot: Iterable[MarketSnapshotItem],
    symbols_list: Iterable[SymbolInfo],
    indicators_map: dict[str, Any],
    fundamentals_map: dict[str, Any],
    params: ScreenerParams,
) -> list[dict[str, Any]]:
    """Return the rows matching `params`, sorted and limited.

    Rows are plain dicts; the caller serialises them as-is.
    """
    meta = {s.symbol: s for s in symbols_list or []}
    rows: list[dict[str, Any]] = []

    for item in snapshot or []:
        sym = item.symbol
        info = meta.get(sym)
        sector = info.sector if info else None

        if params.sector and (sector or "").lower() != params.sector.lower():
            continue

        ind = indicators_map.get(sym)
        fun = fundamentals_map.get(sym)

        pe = _fundamental(fun, "pe")
        pb = _fundamental(fun, "pb")
        roe = _fundamental(fun, "roe")
        div_yield = _fundamental(fun, "div_yield")
        rsi14 = _indicator(ind, "rsi14")
        sma200 = _indicator(ind, "sma200")

        # Each active filter must be satisfiable, so a missing value fails it.
        if params.pe_max is not None and (pe is None or pe > params.pe_max):
            continue
        if params.pb_max is not None and (pb is None or pb > params.pb_max):
            continue
        if params.roe_min is not None and (roe is None or roe < params.roe_min):
            continue
        if params.div_yield_min is not None and (
            div_yield is None or div_yield < params.div_yield_min
        ):
            continue
        if params.rsi_max is not None and (rsi14 is None or rsi14 > params.rsi_max):
            continue
        if params.rsi_min is not None and (rsi14 is None or rsi14 < params.rsi_min):
            continue
        if params.above_sma200 and (
            sma200 is None or item.price is None or item.price <= sma200
        ):
            continue

        rows.append(
            {
                "symbol": sym,
                "name": info.name if info else "",
                "sector": sector,
                "price": item.price,
                "change": item.change,
                "change_pct": item.change_pct,
                "volume": item.volume,
                "pe": pe,
                "pb": pb,
                "roe": roe,
                "div_yield": div_yield,
                "rsi14": rsi14,
                "sma200": sma200,
                "above_sma200": (
                    None
                    if sma200 is None or item.price is None
                    else item.price > sma200
                ),
            }
        )

    sort_by = params.sort_by if params.sort_by in _SORTABLE else "change_pct"
    # Symbols missing the sort metric go last in BOTH directions - an absent
    # value is not a "best" value, so it must never lead a descending sort.
    ranked = [r for r in rows if r.get(sort_by) is not None]
    unranked = [r for r in rows if r.get(sort_by) is None]
    ranked.sort(key=lambda r: r[sort_by], reverse=bool(params.desc))

    limit = params.limit if params.limit and params.limit > 0 else 20
    return (ranked + unranked)[:limit]
