from __future__ import annotations

from app.models import ScreenerParams, MarketSnapshotItem, IndicatorResult, SymbolInfo


def screen_symbols(
    snapshot: list[MarketSnapshotItem],
    symbols: list[SymbolInfo],
    indicators: dict[str, IndicatorResult],
    fundamentals: dict[str, dict],
    params: ScreenerParams,
) -> list[dict]:
    """Apply multi-criteria screening over the universe and return ranked results."""
    sector_map = {s.symbol: s.sector for s in symbols}
    name_map = {s.symbol: s.name for s in symbols}

    results = []
    for item in snapshot:
        sym = item.symbol
        sector = sector_map.get(sym)
        f = fundamentals.get(sym, {})
        ind = indicators.get(sym)
        ind_map = ind.indicators if ind else {}

        # Apply filters
        if params.sector and sector != params.sector:
            continue
        if params.pe_max is not None and f.get("pe") and f["pe"] > params.pe_max:
            continue
        if params.roe_min is not None and f.get("roe") and f["roe"] < params.roe_min:
            continue
        if params.pb_max is not None and f.get("pb") and f["pb"] > params.pb_max:
            continue
        if params.div_yield_min is not None and f.get("div_yield") and f["div_yield"] < params.div_yield_min:
            continue

        # RSI filter
        rsi = ind_map.get("rsi14")
        if params.rsi_max is not None and rsi is not None and rsi > params.rsi_max:
            continue
        if params.rsi_min is not None and rsi is not None and rsi < params.rsi_min:
            continue

        # SMA200 filter
        if params.above_sma200:
            sma200 = ind_map.get("sma200")
            if sma200 is not None and (item.price or 0) <= sma200:
                continue

        results.append({
            "symbol": sym,
            "name": name_map.get(sym, ""),
            "sector": sector,
            "price": item.price,
            "change_pct": item.change_pct,
            "volume": item.volume,
            "rsi14": rsi,
            "pe": f.get("pe"),
        })

    # Sort
    key = params.sort_by
    reverse = params.desc
    if key == "change_pct":
        results.sort(key=lambda x: x.get("change_pct") or 0, reverse=reverse)
    elif key == "rsi14":
        results.sort(key=lambda x: x.get("rsi14") or 0, reverse=reverse)
    elif key == "volume":
        results.sort(key=lambda x: x.get("volume") or 0, reverse=reverse)
    elif key == "pe":
        results.sort(key=lambda x: x.get("pe") or 99999, reverse=not reverse)
    elif key == "composite":
        results.sort(key=lambda x: (x.get("change_pct") or 0) + ((x.get("rsi14") or 50) - 50) * 0.1, reverse=reverse)

    return results[:params.limit]
